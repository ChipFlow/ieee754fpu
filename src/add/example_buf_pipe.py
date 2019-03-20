""" nmigen implementation of buffered pipeline stage, based on zipcpu:
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

from nmigen import Signal, Cat, Const, Mux, Module
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
        passsed a list (or tuple) of objects, and calls the objects' eq
        function.

        complex objects (classes) can be used: they must follow the
        convention of having an eq member function, which takes the
        responsibility of further calling eq and returning a list of
        eq assignments

        Record is a special (unusual, recursive) case, where the input
        is specified as a dictionary (which may contain further dictionaries,
        recursively), where the field names of the dictionary must match
        the Record's field spec.
    """
    if not isinstance(o, Sequence):
        o, i = [o], [i]
    res = []
    for (ao, ai) in zip(o, i):
        #print ("eq", ao, ai)
        if isinstance(ao, Record):
            for idx, (field_name, field_shape, _) in enumerate(ao.layout):
                if isinstance(field_shape, Layout):
                    rres = eq(ao.fields[field_name], ai.fields[field_name])
                else:
                    rres = eq(ao.fields[field_name], ai[field_name])
                res += rres
        else:
            res.append(ao.eq(ai))
    return res


class PipelineBase:
    """ Common functions for Pipeline API
    """
    def __init__(self, stage, in_multi=None):
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
        self.p = PrevControl(in_multi)
        self.n = NextControl()

    def connect_to_next(self, nxt):
        """ helper function to connect to the next stage data/valid/ready.
        """
        return self.n.connect_to_next(nxt.p)

    def connect_in(self, prev):
        """ helper function to connect stage to an input source.  do not
            use to connect stage-to-stage!
        """
        return self.p.connect_in(prev.p)

    def connect_out(self, nxt):
        """ helper function to connect stage to an output source.  do not
            use to connect stage-to-stage!
        """
        return self.n.connect_out(nxt.n)

    def set_input(self, i):
        """ helper function to set the input data
        """
        return eq(self.p.i_data, i)

    def ports(self):
        return [self.p.i_valid, self.n.i_ready,
                self.n.o_valid, self.p.o_ready,
                self.p.i_data, self.n.o_data   # XXX need flattening!
               ]


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
    def __init__(self, stage):
        PipelineBase.__init__(self, stage)

        # set up the input and output data
        self.p.i_data = stage.ispec() # input type
        self.n.o_data = stage.ospec()

    def elaborate(self, platform):
        m = Module()

        result = self.stage.ospec()
        r_data = self.stage.ospec()
        if hasattr(self.stage, "setup"):
            self.stage.setup(m, self.p.i_data)

        # establish some combinatorial temporaries
        p_i_valid = Signal(reset_less=True)
        o_n_validn = Signal(reset_less=True)
        i_p_valid_o_p_ready = Signal(reset_less=True)
        vlen = len(self.p.i_valid)
        if vlen > 1: # multi-bit case: valid only when i_valid is all 1s
            all1s = Const(-1, (len(self.p.i_valid), False))
            m.d.comb += p_i_valid.eq(self.p.i_valid == all1s)
        else: # single-bit i_valid case
            m.d.comb += p_i_valid.eq(self.p.i_valid)
        m.d.comb += [ o_n_validn.eq(~self.n.o_valid),
                     i_p_valid_o_p_ready.eq(p_i_valid & self.p.o_ready),
        ]

        # store result of processing in combinatorial temporary
        #with m.If(self.p.i_valid): # input is valid: process it
        m.d.comb += eq(result, self.stage.process(self.p.i_data))
        # if not in stall condition, update the temporary register
        with m.If(self.p.o_ready): # not stalled
            m.d.sync += eq(r_data, result) # update buffer

        #with m.If(self.p.i_rst): # reset
        #    m.d.sync += self.n.o_valid.eq(0)
        #    m.d.sync += self.p.o_ready.eq(0)
        with m.If(self.n.i_ready): # next stage is ready
            with m.If(self.p.o_ready): # not stalled
                # nothing in buffer: send (processed) input direct to output
                m.d.sync += [self.n.o_valid.eq(p_i_valid),
                             eq(self.n.o_data, result), # update output
                            ]
            with m.Else(): # p.o_ready is false, and something is in buffer.
                # Flush the [already processed] buffer to the output port.
                m.d.sync += [self.n.o_valid.eq(1),
                             eq(self.n.o_data, r_data), # flush buffer
                             # clear stall condition, declare register empty.
                             self.p.o_ready.eq(1),
                            ]
                # ignore input, since p.o_ready is also false.

        # (n.i_ready) is false here: next stage is ready
        with m.Elif(o_n_validn): # next stage being told "ready"
            m.d.sync += [self.n.o_valid.eq(p_i_valid),
                         self.p.o_ready.eq(1), # Keep the buffer empty
                         # set the output data (from comb result)
                         eq(self.n.o_data, result),
                        ]
        # (n.i_ready) false and (n.o_valid) true:
        with m.Elif(i_p_valid_o_p_ready):
            # If next stage *is* ready, and not stalled yet, accept input
            m.d.sync += self.p.o_ready.eq(~(p_i_valid & self.n.o_valid))

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
        return Signal(16)

    def ospec():
        return Signal(16)

    def process(i):
        """ process the input data and returns it (adds 1)
        """
        return i + 1


class ExampleBufPipe(BufferedPipeline):
    """ an example of how to use the buffered pipeline.
    """

    def __init__(self):
        BufferedPipeline.__init__(self, ExampleStage)


class CombPipe(PipelineBase):
    """A simple pipeline stage containing combinational logic that can execute
    completely in one clock cycle.

    Attributes:
    -----------
    input : StageInput
        The pipeline input
    output : StageOutput
        The pipeline output
    r_data : Signal, input_shape
        A temporary (buffered) copy of a prior (valid) input
    result: Signal, output_shape
        The output of the combinatorial logic
    """

    def __init__(self, stage):
        PipelineBase.__init__(self, stage)
        self._data_valid = Signal()

        # set up the input and output data
        self.p.i_data = stage.ispec() # input type
        self.n.o_data = stage.ospec() # output type

    def elaborate(self, platform):
        m = Module()

        r_data = self.stage.ispec() # input type
        result = self.stage.ospec() # output data
        if hasattr(self.stage, "setup"):
            self.stage.setup(m, r_data)

        m.d.comb += eq(result, self.stage.process(r_data))
        m.d.comb += self.n.o_valid.eq(self._data_valid)
        m.d.comb += self.p.o_ready.eq(~self._data_valid | self.n.i_ready)
        m.d.sync += self._data_valid.eq(self.p.i_valid | \
                                        (~self.n.i_ready & self._data_valid))
        with m.If(self.p.i_valid & self.p.o_ready):
            m.d.sync += eq(r_data, self.p.i_data)
        m.d.comb += eq(self.n.o_data, result)
        return m


class ExampleCombPipe(CombPipe):
    """ an example of how to use the combinatorial pipeline.
    """

    def __init__(self):
        CombPipe.__init__(self, ExampleStage)


if __name__ == '__main__':
    dut = ExampleBufPipe()
    vl = rtlil.convert(dut, ports=dut.ports())
    with open("test_bufpipe.il", "w") as f:
        f.write(vl)

    dut = ExampleCombPipe()
    vl = rtlil.convert(dut, ports=dut.ports())
    with open("test_combpipe.il", "w") as f:
        f.write(vl)
