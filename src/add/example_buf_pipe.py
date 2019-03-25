""" Pipeline and BufferedPipeline implementation, conforming to the same API.

    eq:
    --

    a strategically very important function that is identical in function
    to nmigen's Signal.eq function, except it may take objects, or a list
    of objects, or a tuple of objects, and where objects may also be
    Records.

    Stage API:
    ---------

    stage requires compliance with a strict API that may be
    implemented in several means, including as a static class.
    the methods of a stage instance must be as follows:

    * ispec() - Input data format specification
                returns an object or a list or tuple of objects, or
                a Record, each object having an "eq" function which
                takes responsibility for copying by assignment all
                sub-objects
    * ospec() - Output data format specification
                requirements as for ospec
    * process(m, i) - Processes an ispec-formatted object
                returns a combinatorial block of a result that
                may be assigned to the output, by way of the "eq"
                function
    * setup(m, i) - Optional function for setting up submodules
                may be used for more complex stages, to link
                the input (i) to submodules.  must take responsibility
                for adding those submodules to the module (m).
                the submodules must be combinatorial blocks and
                must have their inputs and output linked combinatorially.

    StageChain:
    ----------

    A useful combinatorial wrapper around stages that chains them together
    and then presents a Stage-API-conformant interface.

    UnbufferedPipeline:
    ------------------

    A simple stalling clock-synchronised pipeline that has no buffering
    (unlike BufferedPipeline).  A stall anywhere along the line will
    result in a stall back-propagating down the entire chain.

    The BufferedPipeline by contrast will buffer incoming data, allowing
    previous stages one clock cycle's grace before also having to stall.

    BufferedPipeline:
    ----------------

    nmigen implementation of buffered pipeline stage, based on zipcpu:
    https://zipcpu.com/blog/2017/08/14/strategies-for-pipelining.html

    this module requires quite a bit of thought to understand how it works
    (and why it is needed in the first place).  reading the above is
    *strongly* recommended.

    unlike john dawson's IEEE754 FPU STB/ACK signalling, which requires
    the STB / ACK signals to raise and lower (on separate clocks) before
    data may proceeed (thus only allowing one piece of data to proceed
    on *ALTERNATE* cycles), the signalling here is a true pipeline
    where data will flow on *every* clock when the conditions are right.

    input acceptance conditions are when:
        * incoming previous-stage strobe (p.i_valid) is HIGH
        * outgoing previous-stage ready   (p.o_ready) is LOW

    output transmission conditions are when:
        * outgoing next-stage strobe (n.o_valid) is HIGH
        * outgoing next-stage ready   (n.i_ready) is LOW

    the tricky bit is when the input has valid data and the output is not
    ready to accept it.  if it wasn't for the clock synchronisation, it
    would be possible to tell the input "hey don't send that data, we're
    not ready".  unfortunately, it's not possible to "change the past":
    the previous stage *has no choice* but to pass on its data.

    therefore, the incoming data *must* be accepted - and stored: that
    is the responsibility / contract that this stage *must* accept.
    on the same clock, it's possible to tell the input that it must
    not send any more data.  this is the "stall" condition.

    we now effectively have *two* possible pieces of data to "choose" from:
    the buffered data, and the incoming data.  the decision as to which
    to process and output is based on whether we are in "stall" or not.
    i.e. when the next stage is no longer ready, the output comes from
    the buffer if a stall had previously occurred, otherwise it comes
    direct from processing the input.

    this allows us to respect a synchronous "travelling STB" with what
    dan calls a "buffered handshake".

    it's quite a complex state machine!
"""

from nmigen import Signal, Cat, Const, Mux, Module, Array
from nmigen.cli import verilog, rtlil
from nmigen.hdl.rec import Record, Layout

from collections.abc import Sequence


class PrevControl:
    """ contains signals that come *from* the previous stage (both in and out)
        * i_valid: previous stage indicating all incoming data is valid.
                   may be a multi-bit signal, where all bits are required
                   to be asserted to indicate "valid".
        * o_ready: output to next stage indicating readiness to accept data
        * i_data : an input - added by the user of this class
    """

    def __init__(self, i_width=1):
        self.i_valid = Signal(i_width, name="p_i_valid") # prev   >>in  self
        self.o_ready = Signal(name="p_o_ready") # prev   <<out self

    def connect_in(self, prev):
        """ helper function to connect stage to an input source.  do not
            use to connect stage-to-stage!
        """
        return [self.i_valid.eq(prev.i_valid),
                prev.o_ready.eq(self.o_ready),
                eq(self.i_data, prev.i_data),
               ]

    def i_valid_logic(self):
        vlen = len(self.i_valid)
        if vlen > 1: # multi-bit case: valid only when i_valid is all 1s
            all1s = Const(-1, (len(self.i_valid), False))
            return self.i_valid == all1s
        # single-bit i_valid case
        return self.i_valid


class NextControl:
    """ contains the signals that go *to* the next stage (both in and out)
        * o_valid: output indicating to next stage that data is valid
        * i_ready: input from next stage indicating that it can accept data
        * o_data : an output - added by the user of this class
    """
    def __init__(self):
        self.o_valid = Signal(name="n_o_valid") # self out>>  next
        self.i_ready = Signal(name="n_i_ready") # self <<in   next

    def connect_to_next(self, nxt):
        """ helper function to connect to the next stage data/valid/ready.
            data/valid is passed *TO* nxt, and ready comes *IN* from nxt.
        """
        return [nxt.i_valid.eq(self.o_valid),
                self.i_ready.eq(nxt.o_ready),
                eq(nxt.i_data, self.o_data),
               ]

    def connect_out(self, nxt):
        """ helper function to connect stage to an output source.  do not
            use to connect stage-to-stage!
        """
        return [nxt.o_valid.eq(self.o_valid),
                self.i_ready.eq(nxt.i_ready),
                eq(nxt.o_data, self.o_data),
               ]


def eq(o, i):
    """ makes signals equal: a helper routine which identifies if it is being
        passed a list (or tuple) of objects, or signals, or Records, and calls
        the objects' eq function.

        complex objects (classes) can be used: they must follow the
        convention of having an eq member function, which takes the
        responsibility of further calling eq and returning a list of
        eq assignments

        Record is a special (unusual, recursive) case, where the input may be
        specified as a dictionary (which may contain further dictionaries,
        recursively), where the field names of the dictionary must match
        the Record's field spec.  Alternatively, an object with the same
        member names as the Record may be assigned: it does not have to
        *be* a Record.
    """
    if not isinstance(o, Sequence):
        o, i = [o], [i]
    res = []
    for (ao, ai) in zip(o, i):
        #print ("eq", ao, ai)
        if isinstance(ao, Record):
            for idx, (field_name, field_shape, _) in enumerate(ao.layout):
                if isinstance(field_shape, Layout):
                    val = ai.fields
                else:
                    val = ai
                if hasattr(val, field_name): # check for attribute
                    val = getattr(val, field_name)
                else:
                    val = val[field_name] # dictionary-style specification
                rres = eq(ao.fields[field_name], val)
                res += rres
        else:
            rres = ao.eq(ai)
            if not isinstance(rres, Sequence):
                rres = [rres]
            res += rres
    return res


class StageChain:
    """ pass in a list of stages, and they will automatically be
        chained together via their input and output specs into a
        combinatorial chain.

        * input to this class will be the input of the first stage
        * output of first stage goes into input of second
        * output of second goes into input into third (etc. etc.)
        * the output of this class will be the output of the last stage
    """
    def __init__(self, chain):
        self.chain = chain

    def ispec(self):
        return self.chain[0].ispec()

    def ospec(self):
        return self.chain[-1].ospec()

    def setup(self, m, i):
        for (idx, c) in enumerate(self.chain):
            if hasattr(c, "setup"):
                c.setup(m, i)               # stage may have some module stuff
            o = self.chain[idx].ospec()     # only the last assignment survives
            m.d.comb += eq(o, c.process(i)) # process input into "o"
            if idx != len(self.chain)-1:
                ni = self.chain[idx+1].ispec() # becomes new input on next loop
                m.d.comb += eq(ni, o)          # assign output to next input
                i = ni
        self.o = o                             # last loop is the output

    def process(self, i):
        return self.o


class PipelineBase:
    """ Common functions for Pipeline API
    """
    def __init__(self, stage, in_multi=None, p_len=1, n_len=1):
        """ pass in a "stage" which may be either a static class or a class
            instance, which has four functions (one optional):
            * ispec: returns input signals according to the input specification
            * ispec: returns output signals to the output specification
            * process: takes an input instance and returns processed data
            * setup: performs any module linkage if the stage uses one.

            User must also:
            * add i_data member to PrevControl and
            * add o_data member to NextControl
        """
        self.stage = stage

        # set up input and output IO ACK (prev/next ready/valid)
        p = []
        n = []
        for i in range(p_len):
            p.append(PrevControl(in_multi))
        for i in range(n_len):
            n.append(NextControl())
        if p_len > 1:
            self.p = Array(p)
        else:
            self.p = p
        if n_len > 1:
            self.n = Array(n)
        else:
            self.n = n

    def connect_to_next(self, nxt, p_idx=0, n_idx=0):
        """ helper function to connect to the next stage data/valid/ready.
        """
        return self.n[n_idx].connect_to_next(nxt.p[p_idx])

    def connect_in(self, prev, idx=0, prev_idx=None):
        """ helper function to connect stage to an input source.  do not
            use to connect stage-to-stage!
        """
        if prev_idx is None:
            return self.p[idx].connect_in(prev.p)
        return self.p[idx].connect_in(prev.p[prev_idx])

    def connect_out(self, nxt, idx=0, nxt_idx=None):
        """ helper function to connect stage to an output source.  do not
            use to connect stage-to-stage!
        """
        if nxt_idx is None:
            return self.n[idx].connect_out(nxt.n)
        return self.n[idx].connect_out(nxt.n[nxt+idx])

    def set_input(self, i, idx=0):
        """ helper function to set the input data
        """
        return eq(self.p[idx].i_data, i)

    def ports(self):
        res = []
        for i in range(len(self.p)):
            res += [self.p[i].i_valid, self.p[i].o_ready,
                    self.p[i].i_data]# XXX need flattening!]
        for i in range(len(self.n)):
            res += [self.n[i].i_ready, self.n[i].o_valid,
                    self.n.o_data]   # XXX need flattening!]
        return res


class BufferedPipeline(PipelineBase):
    """ buffered pipeline stage.  data and strobe signals travel in sync.
        if ever the input is ready and the output is not, processed data
        is stored in a temporary register.

        stage-1   p.i_valid >>in   stage   n.o_valid out>>   stage+1
        stage-1   p.o_ready <<out  stage   n.i_ready <<in    stage+1
        stage-1   p.i_data  >>in   stage   n.o_data  out>>   stage+1
                              |             |
                            process --->----^
                              |             |
                              +-- r_data ->-+

        input data p.i_data is read (only), is processed and goes into an
        intermediate result store [process()].  this is updated combinatorially.

        in a non-stall condition, the intermediate result will go into the
        output (update_output).  however if ever there is a stall, it goes
        into r_data instead [update_buffer()].

        when the non-stall condition is released, r_data is the first
        to be transferred to the output [flush_buffer()], and the stall
        condition cleared.

        on the next cycle (as long as stall is not raised again) the
        input may begin to be processed and transferred directly to output.
    """

    def __init__(self, stage, n_len=1, p_len=1, p_mux=None, n_mux=None):
        """ set up a BufferedPipeline (multi-input, multi-output)
            NOTE: n_len > 1 and p_len > 1 is NOT supported

            Arguments:

            * stage: see Stage API above
            * p_len: number of inputs (PrevControls + data)
            * n_len: number of outputs (NextControls + data)
            * p_mux: optional multiplex selector for incoming data
            * n_mux: optional multiplex router for outgoing data
        """
        PipelineBase.__init__(self, stage)
        self.p_mux = p_mux
        self.n_mux = n_mux

        # set up the input and output data
        for i in range(p_len):
            self.p[i].i_data = stage.ispec() # input type
        for i in range(n_len):
            self.n[i].o_data = stage.ospec()

    def elaborate(self, platform):
        m = Module()

        result = self.stage.ospec()
        r_data = self.stage.ospec()
        if hasattr(self.stage, "setup"):
            for i in range(len(self.p)):
                self.stage.setup(m, self.p[i].i_data)

        pi = 0 # TODO: use p_mux to decide which to select
        ni = 0 # TODO: use n_nux to decide which to select

        # establish some combinatorial temporaries
        o_n_validn = Signal(reset_less=True)
        i_p_valid_o_p_ready = Signal(reset_less=True)
        p_i_valid = Signal(reset_less=True)
        m.d.comb += [p_i_valid.eq(self.p[pi].i_valid_logic()),
                     o_n_validn.eq(~self.n[ni].o_valid),
                     i_p_valid_o_p_ready.eq(p_i_valid & self.p[pi].o_ready),
        ]

        # store result of processing in combinatorial temporary
        m.d.comb += eq(result, self.stage.process(self.p[pi].i_data))

        # if not in stall condition, update the temporary register
        with m.If(self.p[pi].o_ready): # not stalled
            m.d.sync += eq(r_data, result) # update buffer

        with m.If(self.n[ni].i_ready): # next stage is ready
            with m.If(self.p[pi].o_ready): # not stalled
                # nothing in buffer: send (processed) input direct to output
                m.d.sync += [self.n[ni].o_valid.eq(p_i_valid),
                             eq(self.n[ni].o_data, result), # update output
                            ]
            with m.Else(): # p.o_ready is false, and something is in buffer.
                # Flush the [already processed] buffer to the output port.
                m.d.sync += [self.n[ni].o_valid.eq(1),      # declare reg empty
                             eq(self.n[ni].o_data, r_data), # flush buffer
                             self.p[pi].o_ready.eq(1),      # clear stall 
                            ]
                # ignore input, since p.o_ready is also false.

        # (n.i_ready) is false here: next stage is ready
        with m.Elif(o_n_validn): # next stage being told "ready"
            m.d.sync += [self.n[ni].o_valid.eq(p_i_valid),
                         self.p[pi].o_ready.eq(1), # Keep the buffer empty
                         eq(self.n[ni].o_data, result), # set output data
                        ]

        # (n.i_ready) false and (n.o_valid) true:
        with m.Elif(i_p_valid_o_p_ready):
            # If next stage *is* ready, and not stalled yet, accept input
            m.d.sync += self.p[pi].o_ready.eq(~(p_i_valid & self.n[ni].o_valid))

        return m


class ExampleAddStage:
    """ an example of how to use the buffered pipeline, as a class instance
    """

    def ispec(self):
        """ returns a tuple of input signals which will be the incoming data
        """
        return (Signal(16), Signal(16))

    def ospec(self):
        """ returns an output signal which will happen to contain the sum
            of the two inputs
        """
        return Signal(16)

    def process(self, i):
        """ process the input data (sums the values in the tuple) and returns it
        """
        return i[0] + i[1]


class ExampleBufPipeAdd(BufferedPipeline):
    """ an example of how to use the buffered pipeline, using a class instance
    """

    def __init__(self):
        addstage = ExampleAddStage()
        BufferedPipeline.__init__(self, addstage)


class ExampleStage:
    """ an example of how to use the buffered pipeline, in a static class
        fashion
    """

    def ispec():
        return Signal(16, name="example_input_signal")

    def ospec():
        return Signal(16, name="example_output_signal")

    def process(i):
        """ process the input data and returns it (adds 1)
        """
        return i + 1


class ExampleStageCls:
    """ an example of how to use the buffered pipeline, in a static class
        fashion
    """

    def ispec(self):
        return Signal(16, name="example_input_signal")

    def ospec(self):
        return Signal(16, name="example_output_signal")

    def process(self, i):
        """ process the input data and returns it (adds 1)
        """
        return i + 1


class ExampleBufPipe(BufferedPipeline):
    """ an example of how to use the buffered pipeline.
    """

    def __init__(self):
        BufferedPipeline.__init__(self, ExampleStage)


class UnbufferedPipeline(PipelineBase):
    """ A simple pipeline stage with single-clock synchronisation
        and two-way valid/ready synchronised signalling.

        Note that a stall in one stage will result in the entire pipeline
        chain stalling.

        Also that unlike BufferedPipeline, the valid/ready signalling does NOT
        travel synchronously with the data: the valid/ready signalling
        combines in a *combinatorial* fashion.  Therefore, a long pipeline
        chain will lengthen propagation delays.

        Argument: stage.  see Stage API, above

        stage-1   p.i_valid >>in   stage   n.o_valid out>>   stage+1
        stage-1   p.o_ready <<out  stage   n.i_ready <<in    stage+1
        stage-1   p.i_data  >>in   stage   n.o_data  out>>   stage+1
                              |             |
                            r_data        result
                              |             |
                              +--process ->-+

        Attributes:
        -----------
        p.i_data : StageInput, shaped according to ispec
            The pipeline input
        p.o_data : StageOutput, shaped according to ospec
            The pipeline output
        r_data : input_shape according to ispec
            A temporary (buffered) copy of a prior (valid) input.
            This is HELD if the output is not ready.  It is updated
            SYNCHRONOUSLY.
        result: output_shape according to ospec
            The output of the combinatorial logic.  it is updated
            COMBINATORIALLY (no clock dependence).
    """

    def __init__(self, stage, p_len=1, n_len=1):
        PipelineBase.__init__(self, stage, p_len, n_len)
        self._data_valid = Signal()

        # set up the input and output data
        for i in range(p_len):
            self.p[i].i_data = stage.ispec() # input type
        for i in range(n_len):
            self.n[i].o_data = stage.ospec()

    def elaborate(self, platform):
        m = Module()

        r_data = []
        result = self.stage.ospec() # output data
        for i in range(len(self.p)):
            r = self.stage.ispec() # input type
            r_data.append(r)
            if hasattr(self.stage, "setup"):
                self.stage.setup(m, r)
        if len(r_data) > 1:
            r_data = Array(r_data)

        pi = 0 # TODO: use p_mux to decide which to select
        ni = 0 # TODO: use n_nux to decide which to select

        p_i_valid = Signal(reset_less=True)
        m.d.comb += p_i_valid.eq(self.p[pi].i_valid_logic())
        m.d.comb += eq(result, self.stage.process(r_data[pi]))
        m.d.comb += self.n[ni].o_valid.eq(self._data_valid)
        m.d.comb += self.p[pi].o_ready.eq(~self._data_valid | \
                                           self.n[ni].i_ready)
        m.d.sync += self._data_valid.eq(p_i_valid | \
                                    (~self.n[ni].i_ready & self._data_valid))
        with m.If(self.p[pi].i_valid & self.p[pi].o_ready):
            m.d.sync += eq(r_data[pi], self.p[pi].i_data)
        m.d.comb += eq(self.n[ni].o_data, result)
        return m


class ExamplePipeline(UnbufferedPipeline):
    """ an example of how to use the combinatorial pipeline.
    """

    def __init__(self):
        UnbufferedPipeline.__init__(self, ExampleStage)


if __name__ == '__main__':
    dut = ExampleBufPipe()
    vl = rtlil.convert(dut, ports=dut.ports())
    with open("test_bufpipe.il", "w") as f:
        f.write(vl)

    dut = ExamplePipeline()
    vl = rtlil.convert(dut, ports=dut.ports())
    with open("test_combpipe.il", "w") as f:
        f.write(vl)
