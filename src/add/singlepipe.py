""" Pipeline and BufferedPipeline implementation, conforming to the same API.
    For multi-input and multi-output variants, see multipipe.

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

    Both StageCls (for use with non-static classes) and Stage (for use
    by static classes) are abstract classes from which, for convenience
    and as a courtesy to other developers, anything conforming to the
    Stage API may *choose* to derive.

    StageChain:
    ----------

    A useful combinatorial wrapper around stages that chains them together
    and then presents a Stage-API-conformant interface.  By presenting
    the same API as the stages it wraps, it can clearly be used recursively.

    RecordBasedStage:
    ----------------

    A convenience class that takes an input shape, output shape, a
    "processing" function and an optional "setup" function.  Honestly
    though, there's not much more effort to just... create a class
    that returns a couple of Records (see ExampleAddRecordStage in
    examples).

    PassThroughStage:
    ----------------

    A convenience class that takes a single function as a parameter,
    that is chain-called to create the exact same input and output spec.
    It has a process() function that simply returns its input.

    Instances of this class are completely redundant if handed to
    StageChain, however when passed to UnbufferedPipeline they
    can be used to introduce a single clock delay.

    ControlBase:
    -----------

    The base class for pipelines.  Contains previous and next ready/valid/data.
    Also has an extremely useful "connect" function that can be used to
    connect a chain of pipelines and present the exact same prev/next
    ready/valid/data API.

    UnbufferedPipeline:
    ------------------

    A simple stalling clock-synchronised pipeline that has no buffering
    (unlike BufferedPipeline).  Data flows on *every* clock cycle when
    the conditions are right (this is nominally when the input is valid
    and the output is ready).

    A stall anywhere along the line will result in a stall back-propagating
    down the entire chain.  The BufferedPipeline by contrast will buffer
    incoming data, allowing previous stages one clock cycle's grace before
    also having to stall.

    An advantage of the UnbufferedPipeline over the Buffered one is
    that the amount of logic needed (number of gates) is greatly
    reduced (no second set of buffers basically)

    The disadvantage of the UnbufferedPipeline is that the valid/ready
    logic, if chained together, is *combinatorial*, resulting in
    progressively larger gate delay.

    RegisterPipeline:
    ----------------

    A convenience class that, because UnbufferedPipeline introduces a single
    clock delay, when its stage is a PassThroughStage, it results in a Pipeline
    stage that, duh, delays its (unmodified) input by one clock cycle.

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

from nmigen import Signal, Cat, Const, Mux, Module, Value
from nmigen.cli import verilog, rtlil
from nmigen.hdl.ast import ArrayProxy
from nmigen.hdl.rec import Record, Layout

from abc import ABCMeta, abstractmethod
from collections.abc import Sequence


class PrevControl:
    """ contains signals that come *from* the previous stage (both in and out)
        * i_valid: previous stage indicating all incoming data is valid.
                   may be a multi-bit signal, where all bits are required
                   to be asserted to indicate "valid".
        * o_ready: output to next stage indicating readiness to accept data
        * i_data : an input - added by the user of this class
    """

    def __init__(self, i_width=1, stage_ctl=False):
        self.stage_ctl = stage_ctl
        self.i_valid = Signal(i_width, name="p_i_valid") # prev   >>in  self
        self._o_ready = Signal(name="p_o_ready") # prev   <<out self
        self.i_data = None # XXX MUST BE ADDED BY USER
        if stage_ctl:
            self.s_o_ready = Signal(name="p_s_o_rdy") # prev   <<out self

    @property
    def o_ready(self):
        """ public-facing API: indicates (externally) that stage is ready
        """
        if self.stage_ctl:
            return self.s_o_ready # set dynamically by stage
        return self._o_ready      # return this when not under dynamic control

    def _connect_in(self, prev):
        """ internal helper function to connect stage to an input source.
            do not use to connect stage-to-stage!
        """
        return [self.i_valid.eq(prev.i_valid_test),
                prev.o_ready.eq(self.o_ready),
                eq(self.i_data, prev.i_data),
               ]

    @property
    def i_valid_test(self):
        vlen = len(self.i_valid)
        if vlen > 1:
            # multi-bit case: valid only when i_valid is all 1s
            all1s = Const(-1, (len(self.i_valid), False))
            i_valid = (self.i_valid == all1s)
        else:
            # single-bit i_valid case
            i_valid = self.i_valid

        # when stage indicates not ready, incoming data
        # must "appear" to be not ready too
        if self.stage_ctl:
            i_valid = i_valid & self.s_o_ready

        return i_valid


class NextControl:
    """ contains the signals that go *to* the next stage (both in and out)
        * o_valid: output indicating to next stage that data is valid
        * i_ready: input from next stage indicating that it can accept data
        * o_data : an output - added by the user of this class
    """
    def __init__(self, stage_ctl=False):
        self.stage_ctl = stage_ctl
        self.o_valid = Signal(name="n_o_valid") # self out>>  next
        self.i_ready = Signal(name="n_i_ready") # self <<in   next
        self.o_data = None # XXX MUST BE ADDED BY USER
        #if self.stage_ctl:
        self.d_valid = Signal(reset=1) # INTERNAL (data valid)

    @property
    def i_ready_test(self):
        if self.stage_ctl:
            return self.i_ready & self.d_valid
        return self.i_ready

    def connect_to_next(self, nxt):
        """ helper function to connect to the next stage data/valid/ready.
            data/valid is passed *TO* nxt, and ready comes *IN* from nxt.
            use this when connecting stage-to-stage
        """
        return [nxt.i_valid.eq(self.o_valid),
                self.i_ready.eq(nxt.o_ready),
                eq(nxt.i_data, self.o_data),
               ]

    def _connect_out(self, nxt):
        """ internal helper function to connect stage to an output source.
            do not use to connect stage-to-stage!
        """
        return [nxt.o_valid.eq(self.o_valid),
                self.i_ready.eq(nxt.i_ready_test),
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

        ArrayProxy is also special-cased, it's a bit messy: whilst ArrayProxy
        has an eq function, the object being assigned to it (e.g. a python
        object) might not.  despite the *input* having an eq function,
        that doesn't help us, because it's the *ArrayProxy* that's being
        assigned to.  so.... we cheat.  use the ports() function of the
        python object, enumerate them, find out the list of Signals that way,
        and assign them.
    """
    res = []
    if isinstance(o, dict):
        for (k, v) in o.items():
            print ("d-eq", v, i[k])
            res.append(v.eq(i[k]))
        return res

    if not isinstance(o, Sequence):
        o, i = [o], [i]
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
        elif isinstance(ao, ArrayProxy) and not isinstance(ai, Value):
            for p in ai.ports():
                op = getattr(ao, p.name)
                #print (op, p, p.name)
                rres = op.eq(p)
                if not isinstance(rres, Sequence):
                    rres = [rres]
                res += rres
        else:
            rres = ao.eq(ai)
            if not isinstance(rres, Sequence):
                rres = [rres]
            res += rres
    return res


class StageCls(metaclass=ABCMeta):
    """ Class-based "Stage" API.  requires instantiation (after derivation)

        see "Stage API" above..  Note: python does *not* require derivation
        from this class.  All that is required is that the pipelines *have*
        the functions listed in this class.  Derivation from this class
        is therefore merely a "courtesy" to maintainers.
    """
    @abstractmethod
    def ispec(self): pass       # REQUIRED
    @abstractmethod
    def ospec(self): pass       # REQUIRED
    #@abstractmethod
    #def setup(self, m, i): pass # OPTIONAL
    @abstractmethod
    def process(self, i): pass  # REQUIRED


class Stage(metaclass=ABCMeta):
    """ Static "Stage" API.  does not require instantiation (after derivation)

        see "Stage API" above.  Note: python does *not* require derivation
        from this class.  All that is required is that the pipelines *have*
        the functions listed in this class.  Derivation from this class
        is therefore merely a "courtesy" to maintainers.
    """
    @staticmethod
    @abstractmethod
    def ispec(): pass

    @staticmethod
    @abstractmethod
    def ospec(): pass

    #@staticmethod
    #@abstractmethod
    #def setup(m, i): pass

    @staticmethod
    @abstractmethod
    def process(i): pass


class RecordBasedStage(Stage):
    """ convenience class which provides a Records-based layout.
        honestly it's a lot easier just to create a direct Records-based
        class (see ExampleAddRecordStage)
    """
    def __init__(self, in_shape, out_shape, processfn, setupfn=None):
        self.in_shape = in_shape
        self.out_shape = out_shape
        self.__process = processfn
        self.__setup = setupfn
    def ispec(self): return Record(self.in_shape)
    def ospec(self): return Record(self.out_shape)
    def process(seif, i): return self.__process(i)
    def setup(seif, m, i): return self.__setup(m, i)


class StageChain(StageCls):
    """ pass in a list of stages, and they will automatically be
        chained together via their input and output specs into a
        combinatorial chain.

        the end result basically conforms to the exact same Stage API.

        * input to this class will be the input of the first stage
        * output of first stage goes into input of second
        * output of second goes into input into third (etc. etc.)
        * the output of this class will be the output of the last stage
    """
    def __init__(self, chain, specallocate=False):
        self.chain = chain
        self.specallocate = specallocate

    def ispec(self):
        return self.chain[0].ispec()

    def ospec(self):
        return self.chain[-1].ospec()

    def setup(self, m, i):
        for (idx, c) in enumerate(self.chain):
            if hasattr(c, "setup"):
                c.setup(m, i)               # stage may have some module stuff
            if self.specallocate:
                o = self.chain[idx].ospec()     # last assignment survives
                m.d.comb += eq(o, c.process(i)) # process input into "o"
            else:
                o = c.process(i) # store input into "o"
            if idx != len(self.chain)-1:
                if self.specallocate:
                    ni = self.chain[idx+1].ispec() # new input on next loop
                    m.d.comb += eq(ni, o)          # assign to next input
                    i = ni
                else:
                    i = o
        self.o = o                             # last loop is the output

    def process(self, i):
        return self.o # conform to Stage API: return last-loop output


class ControlBase:
    """ Common functions for Pipeline API
    """
    def __init__(self, in_multi=None, stage_ctl=False):
        """ Base class containing ready/valid/data to previous and next stages

            * p: contains ready/valid to the previous stage
            * n: contains ready/valid to the next stage

            Except when calling Controlbase.connect(), user must also:
            * add i_data member to PrevControl (p) and
            * add o_data member to NextControl (n)
        """
        # set up input and output IO ACK (prev/next ready/valid)
        self.p = PrevControl(in_multi, stage_ctl)
        self.n = NextControl(stage_ctl)

    def connect_to_next(self, nxt):
        """ helper function to connect to the next stage data/valid/ready.
        """
        return self.n.connect_to_next(nxt.p)

    def _connect_in(self, prev):
        """ internal helper function to connect stage to an input source.
            do not use to connect stage-to-stage!
        """
        return self.p._connect_in(prev.p)

    def _connect_out(self, nxt):
        """ internal helper function to connect stage to an output source.
            do not use to connect stage-to-stage!
        """
        return self.n._connect_out(nxt.n)

    def connect(self, pipechain):
        """ connects a chain (list) of Pipeline instances together and
            links them to this ControlBase instance:

                      in <----> self <---> out
                       |                   ^
                       v                   |
                    [pipe1, pipe2, pipe3, pipe4]
                       |    ^  |    ^  |     ^
                       v    |  v    |  v     |
                     out---in out--in out---in

            Also takes care of allocating i_data/o_data, by looking up
            the data spec for each end of the pipechain.  i.e It is NOT
            necessary to allocate self.p.i_data or self.n.o_data manually:
            this is handled AUTOMATICALLY, here.

            Basically this function is the direct equivalent of StageChain,
            except that unlike StageChain, the Pipeline logic is followed.

            Just as StageChain presents an object that conforms to the
            Stage API from a list of objects that also conform to the
            Stage API, an object that calls this Pipeline connect function
            has the exact same pipeline API as the list of pipline objects
            it is called with.

            Thus it becomes possible to build up larger chains recursively.
            More complex chains (multi-input, multi-output) will have to be
            done manually.
        """
        eqs = [] # collated list of assignment statements

        # connect inter-chain
        for i in range(len(pipechain)-1):
            pipe1 = pipechain[i]
            pipe2 = pipechain[i+1]
            eqs += pipe1.connect_to_next(pipe2)

        # connect front of chain to ourselves
        front = pipechain[0]
        self.p.i_data = front.stage.ispec()
        eqs += front._connect_in(self)

        # connect end of chain to ourselves
        end = pipechain[-1]
        self.n.o_data = end.stage.ospec()
        eqs += end._connect_out(self)

        return eqs

    def set_input(self, i):
        """ helper function to set the input data
        """
        return eq(self.p.i_data, i)

    def ports(self):
        res = [self.p.i_valid, self.n.i_ready,
                self.n.o_valid, self.p.o_ready,
               ]
        if hasattr(self.p.i_data, "ports"):
            res += self.p.i_data.ports()
        else:
            res += self.p.i_data
        if hasattr(self.n.o_data, "ports"):
            res += self.n.o_data.ports()
        else:
            res += self.n.o_data
        return res

    def _elaborate(self, platform):
        """ handles case where stage has dynamic ready/valid functions
        """
        m = Module()
        if not self.p.stage_ctl:
            return m

        # intercept the previous (outgoing) "ready", combine with stage ready
        m.d.comb += self.p.s_o_ready.eq(self.p._o_ready & self.stage.d_ready)

        # intercept the next (incoming) "ready" and combine it with data valid
        m.d.comb += self.n.d_valid.eq(self.n.i_ready & self.stage.d_valid)

        return m


class BufferedPipeline(ControlBase):
    """ buffered pipeline stage.  data and strobe signals travel in sync.
        if ever the input is ready and the output is not, processed data
        is shunted in a temporary register.

        Argument: stage.  see Stage API above

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
    def __init__(self, stage, stage_ctl=False, buffermode=True):
        ControlBase.__init__(self, stage_ctl=stage_ctl)
        self.stage = stage
        self.buffermode = buffermode

        # set up the input and output data
        self.p.i_data = stage.ispec() # input type
        self.n.o_data = stage.ospec()

    def elaborate(self, platform):

        self.m = ControlBase._elaborate(self, platform)

        result = self.stage.ospec()
        if self.buffermode:
            r_data = self.stage.ospec()
        if hasattr(self.stage, "setup"):
            self.stage.setup(self.m, self.p.i_data)

        # establish some combinatorial temporaries
        o_n_validn = Signal(reset_less=True)
        n_i_ready = Signal(reset_less=True, name="n_i_rdy_data")
        i_p_valid_o_p_ready = Signal(reset_less=True)
        p_i_valid = Signal(reset_less=True)
        self.m.d.comb += [p_i_valid.eq(self.p.i_valid_test),
                     o_n_validn.eq(~self.n.o_valid),
                     i_p_valid_o_p_ready.eq(p_i_valid & self.p.o_ready),
                     n_i_ready.eq(self.n.i_ready_test),
        ]

        # store result of processing in combinatorial temporary
        self.m.d.comb += eq(result, self.stage.process(self.p.i_data))

        if self.buffermode:
            # if not in stall condition, update the temporary register
            with self.m.If(self.p.o_ready): # not stalled
                self.m.d.sync += eq(r_data, result) # update buffer

        with self.m.If(n_i_ready): # next stage is ready
            with self.m.If(self.p._o_ready): # not stalled
                # nothing in buffer: send (processed) input direct to output
                self.m.d.sync += [self.n.o_valid.eq(p_i_valid),
                                  eq(self.n.o_data, result), # update output
                            ]
            if self.buffermode:
                with self.m.Else(): # p.o_ready is false, and data in buffer
                    # Flush the [already processed] buffer to the output port.
                    self.m.d.sync += [self.n.o_valid.eq(1),  # reg empty
                                  eq(self.n.o_data, r_data), # flush buffer
                                  self.p._o_ready.eq(1),     # clear stall
                            ]
                # ignore input, since p.o_ready is also false.

        # (n.i_ready) is false here: next stage is ready
        with self.m.Elif(o_n_validn): # next stage being told "ready"
            self.m.d.sync += [self.n.o_valid.eq(p_i_valid),
                              self.p._o_ready.eq(1), # Keep the buffer empty
                              eq(self.n.o_data, result), # set output data
                        ]

        # (n.i_ready) false and (n.o_valid) true:
        with self.m.Elif(i_p_valid_o_p_ready):
            # If next stage *is* ready, and not stalled yet, accept input
            self.m.d.sync += self.p._o_ready.eq(~(p_i_valid & self.n.o_valid))

        return self.m


class BufferedPipeline2(ControlBase):
    """ buffered pipeline stage.  data and strobe signals travel in sync.
        if ever the input is ready and the output is not, processed data
        is shunted in a temporary register.

        Argument: stage.  see Stage API above

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
    def __init__(self, stage, stage_ctl=False):
        ControlBase.__init__(self, stage_ctl=stage_ctl)
        self.stage = stage

        # set up the input and output data
        self.p.i_data = stage.ispec() # input type
        self.n.o_data = stage.ospec()

    def elaborate(self, platform):

        self.m = ControlBase._elaborate(self, platform)

        result = self.stage.ospec()
        r_busy = Signal(reset=0)
        if hasattr(self.stage, "setup"):
            self.stage.setup(self.m, self.p.i_data)

        # establish some combinatorial temporaries
        o_n_validn = Signal(reset_less=True)
        n_i_ready = Signal(reset_less=True, name="n_i_rdy_data")
        o_n_valid_i_n_ready = Signal(reset_less=True)
        p_i_valid = Signal(reset_less=True)
        self.m.d.comb += [p_i_valid.eq(self.p.i_valid_test),
                     o_n_validn.eq(~self.n.o_valid),
                     n_i_ready.eq(self.n.i_ready_test),
                     o_n_valid_i_n_ready.eq(self.n.o_valid & n_i_ready),
        ]

        # store result of processing in combinatorial temporary
        self.m.d.comb += eq(result, self.stage.process(self.p.i_data))

        with self.m.If(self.p.o_ready): # output is ready
            with self.m.If(p_i_valid):   # and input is valid
                self.m.d.sync += [r_busy.eq(1),
                                  eq(self.n.o_data, result), # update output
                                 ]
            # else stay in idle condition (output ready, but input wasn't valid)

        # output valid but not ready, and input is ready
        with self.m.Elif(o_n_valid_i_n_ready):
            # output transaction just took place
            self.m.d.sync += [r_busy.eq(0),
                              self.n.o_valid.eq(0), # set output invalid
                             ]
        # 
        with self.m.Elif(o_n_validn):
            # can check here for data valid
            self.m.d.sync += [self.n.o_valid.eq(1),
                              #eq(self.n.o_data, result), # update output
                       ]

        #self.m.d.comb += self.p._o_ready.eq(~r_busy)
        self.m.d.comb += self.p._o_ready.eq(~(((~n_i_ready)&(self.n.o_valid))| \
                                            (r_busy)))
        return self.m


class UnbufferedPipeline(ControlBase):
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

    def __init__(self, stage, stage_ctl=False):
        ControlBase.__init__(self, stage_ctl=stage_ctl)
        self.stage = stage

        # set up the input and output data
        self.p.i_data = stage.ispec() # input type
        self.n.o_data = stage.ospec() # output type

    def elaborate(self, platform):
        self.m = ControlBase._elaborate(self, platform)

        data_valid = Signal() # is data valid or not
        r_data = self.stage.ispec() # input type
        if hasattr(self.stage, "setup"):
            self.stage.setup(self.m, r_data)

        # some temporaries
        p_i_valid = Signal(reset_less=True)
        pv = Signal(reset_less=True)
        self.m.d.comb += p_i_valid.eq(self.p.i_valid_test)
        self.m.d.comb += pv.eq(self.p.i_valid & self.p.o_ready)

        self.m.d.comb += self.n.o_valid.eq(data_valid)
        self.m.d.comb += self.p._o_ready.eq(~data_valid | self.n.i_ready_test)
        self.m.d.sync += data_valid.eq(p_i_valid | \
                                        (~self.n.i_ready_test & data_valid))
        with self.m.If(pv):
            self.m.d.sync += eq(r_data, self.p.i_data)
        self.m.d.comb += eq(self.n.o_data, self.stage.process(r_data))
        return self.m


class UnbufferedPipeline2(ControlBase):
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
        buf : output_shape according to ospec
            A temporary (buffered) copy of a valid output
            This is HELD if the output is not ready.  It is updated
            SYNCHRONOUSLY.
    """

    def __init__(self, stage, stage_ctl=False):
        ControlBase.__init__(self, stage_ctl=stage_ctl)
        self.stage = stage

        # set up the input and output data
        self.p.i_data = stage.ispec() # input type
        self.n.o_data = stage.ospec() # output type

    def elaborate(self, platform):
        self.m = ControlBase._elaborate(self, platform)

        buf_full = Signal() # is data valid or not
        buf = self.stage.ospec() # output type
        if hasattr(self.stage, "setup"):
            self.stage.setup(self.m, self.p.i_data)

        # some temporaries
        p_i_valid = Signal(reset_less=True)
        self.m.d.comb += p_i_valid.eq(self.p.i_valid_test)

        self.m.d.comb += self.n.o_valid.eq(buf_full | p_i_valid)
        self.m.d.comb += self.p._o_ready.eq(~buf_full)
        self.m.d.sync += buf_full.eq(~self.n.i_ready_test & \
                                        (p_i_valid | buf_full))
        with self.m.If(buf_full):
            self.m.d.comb += eq(self.n.o_data, buf)
        with self.m.Else():
            self.m.d.comb += eq(self.n.o_data,
                                self.stage.process(self.p.i_data))
        self.m.d.sync += eq(buf, self.n.o_data)

        return self.m


class PassThroughStage(StageCls):
    """ a pass-through stage which has its input data spec equal to its output,
        and "passes through" its data from input to output.
    """
    def __init__(self, iospecfn):
        self.iospecfn = iospecfn
    def ispec(self): return self.iospecfn()
    def ospec(self): return self.iospecfn()
    def process(self, i): return i


class RegisterPipeline(UnbufferedPipeline):
    """ A pipeline stage that delays by one clock cycle, creating a
        sync'd latch out of o_data and o_valid as an indirect byproduct
        of using PassThroughStage
    """
    def __init__(self, iospecfn):
        UnbufferedPipeline.__init__(self, PassThroughStage(iospecfn))

