""" Pipeline API.  For multi-input and multi-output variants, see multipipe.

    Associated development bugs:
    * http://bugs.libre-riscv.org/show_bug.cgi?id=64
    * http://bugs.libre-riscv.org/show_bug.cgi?id=57

    Important: see Stage API (stageapi.py) in combination with below

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

    Note: pipelines basically do not become pipelines as such until
    handed to a derivative of ControlBase.  ControlBase itself is *not*
    strictly considered a pipeline class.  Wishbone and AXI4 (master or
    slave) could be derived from ControlBase, for example.
    UnbufferedPipeline:
    ------------------

    A simple stalling clock-synchronised pipeline that has no buffering
    (unlike BufferedHandshake).  Data flows on *every* clock cycle when
    the conditions are right (this is nominally when the input is valid
    and the output is ready).

    A stall anywhere along the line will result in a stall back-propagating
    down the entire chain.  The BufferedHandshake by contrast will buffer
    incoming data, allowing previous stages one clock cycle's grace before
    also having to stall.

    An advantage of the UnbufferedPipeline over the Buffered one is
    that the amount of logic needed (number of gates) is greatly
    reduced (no second set of buffers basically)

    The disadvantage of the UnbufferedPipeline is that the valid/ready
    logic, if chained together, is *combinatorial*, resulting in
    progressively larger gate delay.

    PassThroughHandshake:
    ------------------

    A Control class that introduces a single clock delay, passing its
    data through unaltered.  Unlike RegisterPipeline (which relies
    on UnbufferedPipeline and PassThroughStage) it handles ready/valid
    itself.

    RegisterPipeline:
    ----------------

    A convenience class that, because UnbufferedPipeline introduces a single
    clock delay, when its stage is a PassThroughStage, it results in a Pipeline
    stage that, duh, delays its (unmodified) input by one clock cycle.

    BufferedHandshake:
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
        * incoming previous-stage strobe (p.valid_i) is HIGH
        * outgoing previous-stage ready   (p.ready_o) is LOW

    output transmission conditions are when:
        * outgoing next-stage strobe (n.valid_o) is HIGH
        * outgoing next-stage ready   (n.ready_i) is LOW

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

    SimpleHandshake
    ---------------

    Synchronised pipeline, Based on:
    https://github.com/ZipCPU/dbgbus/blob/master/hexbus/rtl/hbdeword.v
"""

from nmigen import Signal, Mux, Module, Elaboratable, Const
from nmigen.cli import verilog, rtlil
from nmigen.hdl.rec import Record

from nmutil.queue import Queue
import inspect

from nmutil.iocontrol import (PrevControl, NextControl, Object, RecordObject)
from nmutil.stageapi import (_spec, StageCls, Stage, StageChain, StageHelper)
from nmutil import nmoperator


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


class PassThroughStage(StageCls):
    """ a pass-through stage with its input data spec identical to its output,
        and "passes through" its data from input to output (does nothing).

        use this basically to explicitly make any data spec Stage-compliant.
        (many APIs would potentially use a static "wrap" method in e.g.
         StageCls to achieve a similar effect)
    """
    def __init__(self, iospecfn): self.iospecfn = iospecfn
    def ispec(self): return self.iospecfn()
    def ospec(self): return self.iospecfn()


class ControlBase(StageHelper, Elaboratable):
    """ Common functions for Pipeline API.  Note: a "pipeline stage" only
        exists (conceptually) when a ControlBase derivative is handed
        a Stage (combinatorial block)

        NOTE: ControlBase derives from StageHelper, making it accidentally
        compliant with the Stage API.  Using those functions directly
        *BYPASSES* a ControlBase instance ready/valid signalling, which
        clearly should not be done without a really, really good reason.
    """
    def __init__(self, stage=None, in_multi=None, stage_ctl=False, maskwid=0):
        """ Base class containing ready/valid/data to previous and next stages

            * p: contains ready/valid to the previous stage
            * n: contains ready/valid to the next stage

            Except when calling Controlbase.connect(), user must also:
            * add data_i member to PrevControl (p) and
            * add data_o member to NextControl (n)
            Calling ControlBase._new_data is a good way to do that.
        """
        print ("ControlBase", self, stage, in_multi, stage_ctl)
        StageHelper.__init__(self, stage)

        # set up input and output IO ACK (prev/next ready/valid)
        self.p = PrevControl(in_multi, stage_ctl, maskwid=maskwid)
        self.n = NextControl(stage_ctl, maskwid=maskwid)

        # set up the input and output data
        if stage is not None:
            self._new_data("data")

    def _new_data(self, name):
        """ allocates new data_i and data_o
        """
        self.p.data_i, self.n.data_o = self.new_specs(name)

    @property
    def data_r(self):
        return self.process(self.p.data_i)

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

            Also takes care of allocating data_i/data_o, by looking up
            the data spec for each end of the pipechain.  i.e It is NOT
            necessary to allocate self.p.data_i or self.n.data_o manually:
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

            Argument:

            * :pipechain: - a sequence of ControlBase-derived classes
                            (must be one or more in length)

            Returns:

            * a list of eq assignments that will need to be added in
              an elaborate() to m.d.comb
        """
        assert len(pipechain) > 0, "pipechain must be non-zero length"
        assert self.stage is None, "do not use connect with a stage"
        eqs = [] # collated list of assignment statements

        # connect inter-chain
        for i in range(len(pipechain)-1):
            pipe1 = pipechain[i]                # earlier
            pipe2 = pipechain[i+1]              # later (by 1)
            eqs += pipe1.connect_to_next(pipe2) # earlier n to later p

        # connect front and back of chain to ourselves
        front = pipechain[0]                # first in chain
        end = pipechain[-1]                 # last in chain
        self.set_specs(front, end) # sets up ispec/ospec functions
        self._new_data("chain") # NOTE: REPLACES existing data
        eqs += front._connect_in(self)      # front p to our p
        eqs += end._connect_out(self)       # end n   to our n

        return eqs

    def set_input(self, i):
        """ helper function to set the input data (used in unit tests)
        """
        return nmoperator.eq(self.p.data_i, i)

    def __iter__(self):
        yield from self.p # yields ready/valid/data (data also gets yielded)
        yield from self.n # ditto

    def ports(self):
        return list(self)

    def elaborate(self, platform):
        """ handles case where stage has dynamic ready/valid functions
        """
        m = Module()
        m.submodules.p = self.p
        m.submodules.n = self.n

        self.setup(m, self.p.data_i)

        if not self.p.stage_ctl:
            return m

        # intercept the previous (outgoing) "ready", combine with stage ready
        m.d.comb += self.p.s_ready_o.eq(self.p._ready_o & self.stage.d_ready)

        # intercept the next (incoming) "ready" and combine it with data valid
        sdv = self.stage.d_valid(self.n.ready_i)
        m.d.comb += self.n.d_valid.eq(self.n.ready_i & sdv)

        return m


class BufferedHandshake(ControlBase):
    """ buffered pipeline stage.  data and strobe signals travel in sync.
        if ever the input is ready and the output is not, processed data
        is shunted in a temporary register.

        Argument: stage.  see Stage API above

        stage-1   p.valid_i >>in   stage   n.valid_o out>>   stage+1
        stage-1   p.ready_o <<out  stage   n.ready_i <<in    stage+1
        stage-1   p.data_i  >>in   stage   n.data_o  out>>   stage+1
                              |             |
                            process --->----^
                              |             |
                              +-- r_data ->-+

        input data p.data_i is read (only), is processed and goes into an
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

    def elaborate(self, platform):
        self.m = ControlBase.elaborate(self, platform)

        result = _spec(self.stage.ospec, "r_tmp")
        r_data = _spec(self.stage.ospec, "r_data")

        # establish some combinatorial temporaries
        o_n_validn = Signal(reset_less=True)
        n_ready_i = Signal(reset_less=True, name="n_i_rdy_data")
        nir_por = Signal(reset_less=True)
        nir_por_n = Signal(reset_less=True)
        p_valid_i = Signal(reset_less=True)
        nir_novn = Signal(reset_less=True)
        nirn_novn = Signal(reset_less=True)
        por_pivn = Signal(reset_less=True)
        npnn = Signal(reset_less=True)
        self.m.d.comb += [p_valid_i.eq(self.p.valid_i_test),
                     o_n_validn.eq(~self.n.valid_o),
                     n_ready_i.eq(self.n.ready_i_test),
                     nir_por.eq(n_ready_i & self.p._ready_o),
                     nir_por_n.eq(n_ready_i & ~self.p._ready_o),
                     nir_novn.eq(n_ready_i | o_n_validn),
                     nirn_novn.eq(~n_ready_i & o_n_validn),
                     npnn.eq(nir_por | nirn_novn),
                     por_pivn.eq(self.p._ready_o & ~p_valid_i)
        ]

        # store result of processing in combinatorial temporary
        self.m.d.comb += nmoperator.eq(result, self.data_r)

        # if not in stall condition, update the temporary register
        with self.m.If(self.p.ready_o): # not stalled
            self.m.d.sync += nmoperator.eq(r_data, result) # update buffer

        # data pass-through conditions
        with self.m.If(npnn):
            data_o = self._postprocess(result) # XXX TBD, does nothing right now
            self.m.d.sync += [self.n.valid_o.eq(p_valid_i), # valid if p_valid
                              nmoperator.eq(self.n.data_o, data_o), # update out
                             ]
        # buffer flush conditions (NOTE: can override data passthru conditions)
        with self.m.If(nir_por_n): # not stalled
            # Flush the [already processed] buffer to the output port.
            data_o = self._postprocess(r_data) # XXX TBD, does nothing right now
            self.m.d.sync += [self.n.valid_o.eq(1),  # reg empty
                              nmoperator.eq(self.n.data_o, data_o), # flush
                             ]
        # output ready conditions
        self.m.d.sync += self.p._ready_o.eq(nir_novn | por_pivn)

        return self.m


class MaskCancellable(ControlBase):
    """ Mask-activated Cancellable pipeline

        Argument: stage.  see Stage API above

        stage-1   p.valid_i >>in   stage   n.valid_o out>>   stage+1
        stage-1   p.ready_o <<out  stage   n.ready_i <<in    stage+1
        stage-1   p.data_i  >>in   stage   n.data_o  out>>   stage+1
                              |             |
                              +--process->--^
    """
    def __init__(self, stage, maskwid, in_multi=None, stage_ctl=False):
        ControlBase.__init__(self, stage, in_multi, stage_ctl, maskwid)


    def elaborate(self, platform):
        self.m = m = ControlBase.elaborate(self, platform)

        # store result of processing in combinatorial temporary
        result = _spec(self.stage.ospec, "r_tmp")
        m.d.comb += nmoperator.eq(result, self.data_r)

        # establish if the data should be passed on.  cancellation is
        # a global signal.
        # XXX EXCEPTIONAL CIRCUMSTANCES: inspection of the data payload
        # is NOT "normal" for the Stage API.
        p_valid_i = Signal(reset_less=True)
        #print ("self.p.data_i", self.p.data_i)
        m.d.comb += p_valid_i.eq(((self.p.mask_i & ~self.cancelmask).bool()))

        # if idmask nonzero, mask gets passed on (and register set).
        # register is left as-is if idmask is zero, but out-mask is set to zero
        m.d.sync += self.n.valid_o.eq(p_valid_i)
        m.d.sync += self.n.mask_o.eq(Mux(p_valid_i, self.p.mask_i, 0))
        with m.If(p_valid_i):
            data_o = self._postprocess(result) # XXX TBD, does nothing right now
            m.d.sync += nmoperator.eq(self.n.data_o, data_o) # update output

        # output valid if
        # input always "ready"
        #m.d.comb += self.p._ready_o.eq(self.n.ready_i_test)
        m.d.comb += self.p._ready_o.eq(Const(1))

        return self.m


class SimpleHandshake(ControlBase):
    """ simple handshake control.  data and strobe signals travel in sync.
        implements the protocol used by Wishbone and AXI4.

        Argument: stage.  see Stage API above

        stage-1   p.valid_i >>in   stage   n.valid_o out>>   stage+1
        stage-1   p.ready_o <<out  stage   n.ready_i <<in    stage+1
        stage-1   p.data_i  >>in   stage   n.data_o  out>>   stage+1
                              |             |
                              +--process->--^
        Truth Table

        Inputs   Temporary  Output Data
        -------  ---------- -----  ----
        P P N N  PiV& ~NiR&  N P
        i o i o  PoR  NoV    o o
        V R R V              V R

        -------   -    -     - -
        0 0 0 0   0    0    >0 0    reg
        0 0 0 1   0    1    >1 0    reg
        0 0 1 0   0    0     0 1    process(data_i)
        0 0 1 1   0    0     0 1    process(data_i)
        -------   -    -     - -
        0 1 0 0   0    0    >0 0    reg
        0 1 0 1   0    1    >1 0    reg
        0 1 1 0   0    0     0 1    process(data_i)
        0 1 1 1   0    0     0 1    process(data_i)
        -------   -    -     - -
        1 0 0 0   0    0    >0 0    reg
        1 0 0 1   0    1    >1 0    reg
        1 0 1 0   0    0     0 1    process(data_i)
        1 0 1 1   0    0     0 1    process(data_i)
        -------   -    -     - -
        1 1 0 0   1    0     1 0    process(data_i)
        1 1 0 1   1    1     1 0    process(data_i)
        1 1 1 0   1    0     1 1    process(data_i)
        1 1 1 1   1    0     1 1    process(data_i)
        -------   -    -     - -
    """

    def elaborate(self, platform):
        self.m = m = ControlBase.elaborate(self, platform)

        r_busy = Signal()
        result = _spec(self.stage.ospec, "r_tmp")

        # establish some combinatorial temporaries
        n_ready_i = Signal(reset_less=True, name="n_i_rdy_data")
        p_valid_i_p_ready_o = Signal(reset_less=True)
        p_valid_i = Signal(reset_less=True)
        m.d.comb += [p_valid_i.eq(self.p.valid_i_test),
                     n_ready_i.eq(self.n.ready_i_test),
                     p_valid_i_p_ready_o.eq(p_valid_i & self.p.ready_o),
        ]

        # store result of processing in combinatorial temporary
        m.d.comb += nmoperator.eq(result, self.data_r)

        # previous valid and ready
        with m.If(p_valid_i_p_ready_o):
            data_o = self._postprocess(result) # XXX TBD, does nothing right now
            m.d.sync += [r_busy.eq(1),      # output valid
                         nmoperator.eq(self.n.data_o, data_o), # update output
                        ]
        # previous invalid or not ready, however next is accepting
        with m.Elif(n_ready_i):
            data_o = self._postprocess(result) # XXX TBD, does nothing right now
            m.d.sync += [nmoperator.eq(self.n.data_o, data_o)]
            # TODO: could still send data here (if there was any)
            #m.d.sync += self.n.valid_o.eq(0) # ...so set output invalid
            m.d.sync += r_busy.eq(0) # ...so set output invalid

        m.d.comb += self.n.valid_o.eq(r_busy)
        # if next is ready, so is previous
        m.d.comb += self.p._ready_o.eq(n_ready_i)

        return self.m


class UnbufferedPipeline(ControlBase):
    """ A simple pipeline stage with single-clock synchronisation
        and two-way valid/ready synchronised signalling.

        Note that a stall in one stage will result in the entire pipeline
        chain stalling.

        Also that unlike BufferedHandshake, the valid/ready signalling does NOT
        travel synchronously with the data: the valid/ready signalling
        combines in a *combinatorial* fashion.  Therefore, a long pipeline
        chain will lengthen propagation delays.

        Argument: stage.  see Stage API, above

        stage-1   p.valid_i >>in   stage   n.valid_o out>>   stage+1
        stage-1   p.ready_o <<out  stage   n.ready_i <<in    stage+1
        stage-1   p.data_i  >>in   stage   n.data_o  out>>   stage+1
                              |             |
                            r_data        result
                              |             |
                              +--process ->-+

        Attributes:
        -----------
        p.data_i : StageInput, shaped according to ispec
            The pipeline input
        p.data_o : StageOutput, shaped according to ospec
            The pipeline output
        r_data : input_shape according to ispec
            A temporary (buffered) copy of a prior (valid) input.
            This is HELD if the output is not ready.  It is updated
            SYNCHRONOUSLY.
        result: output_shape according to ospec
            The output of the combinatorial logic.  it is updated
            COMBINATORIALLY (no clock dependence).

        Truth Table

        Inputs  Temp  Output  Data
        -------   -   -----   ----
        P P N N ~NiR&  N P
        i o i o  NoV   o o
        V R R V        V R

        -------   -    - -
        0 0 0 0   0    0 1    reg
        0 0 0 1   1    1 0    reg
        0 0 1 0   0    0 1    reg
        0 0 1 1   0    0 1    reg
        -------   -    - -
        0 1 0 0   0    0 1    reg
        0 1 0 1   1    1 0    reg
        0 1 1 0   0    0 1    reg
        0 1 1 1   0    0 1    reg
        -------   -    - -
        1 0 0 0   0    1 1    reg
        1 0 0 1   1    1 0    reg
        1 0 1 0   0    1 1    reg
        1 0 1 1   0    1 1    reg
        -------   -    - -
        1 1 0 0   0    1 1    process(data_i)
        1 1 0 1   1    1 0    process(data_i)
        1 1 1 0   0    1 1    process(data_i)
        1 1 1 1   0    1 1    process(data_i)
        -------   -    - -

        Note: PoR is *NOT* involved in the above decision-making.
    """

    def elaborate(self, platform):
        self.m = m = ControlBase.elaborate(self, platform)

        data_valid = Signal() # is data valid or not
        r_data = _spec(self.stage.ospec, "r_tmp") # output type

        # some temporaries
        p_valid_i = Signal(reset_less=True)
        pv = Signal(reset_less=True)
        buf_full = Signal(reset_less=True)
        m.d.comb += p_valid_i.eq(self.p.valid_i_test)
        m.d.comb += pv.eq(self.p.valid_i & self.p.ready_o)
        m.d.comb += buf_full.eq(~self.n.ready_i_test & data_valid)

        m.d.comb += self.n.valid_o.eq(data_valid)
        m.d.comb += self.p._ready_o.eq(~data_valid | self.n.ready_i_test)
        m.d.sync += data_valid.eq(p_valid_i | buf_full)

        with m.If(pv):
            m.d.sync += nmoperator.eq(r_data, self.data_r)
        data_o = self._postprocess(r_data) # XXX TBD, does nothing right now
        m.d.comb += nmoperator.eq(self.n.data_o, data_o)

        return self.m


class UnbufferedPipeline2(ControlBase):
    """ A simple pipeline stage with single-clock synchronisation
        and two-way valid/ready synchronised signalling.

        Note that a stall in one stage will result in the entire pipeline
        chain stalling.

        Also that unlike BufferedHandshake, the valid/ready signalling does NOT
        travel synchronously with the data: the valid/ready signalling
        combines in a *combinatorial* fashion.  Therefore, a long pipeline
        chain will lengthen propagation delays.

        Argument: stage.  see Stage API, above

        stage-1   p.valid_i >>in   stage   n.valid_o out>>   stage+1
        stage-1   p.ready_o <<out  stage   n.ready_i <<in    stage+1
        stage-1   p.data_i  >>in   stage   n.data_o  out>>   stage+1
                              |             |    |
                              +- process-> buf <-+
        Attributes:
        -----------
        p.data_i : StageInput, shaped according to ispec
            The pipeline input
        p.data_o : StageOutput, shaped according to ospec
            The pipeline output
        buf : output_shape according to ospec
            A temporary (buffered) copy of a valid output
            This is HELD if the output is not ready.  It is updated
            SYNCHRONOUSLY.

        Inputs  Temp  Output Data
        -------   -   -----
        P P N N ~NiR&  N P   (buf_full)
        i o i o  NoV   o o
        V R R V        V R

        -------   -    - -
        0 0 0 0   0    0 1   process(data_i)
        0 0 0 1   1    1 0   reg (odata, unchanged)
        0 0 1 0   0    0 1   process(data_i)
        0 0 1 1   0    0 1   process(data_i)
        -------   -    - -
        0 1 0 0   0    0 1   process(data_i)
        0 1 0 1   1    1 0   reg (odata, unchanged)
        0 1 1 0   0    0 1   process(data_i)
        0 1 1 1   0    0 1   process(data_i)
        -------   -    - -
        1 0 0 0   0    1 1   process(data_i)
        1 0 0 1   1    1 0   reg (odata, unchanged)
        1 0 1 0   0    1 1   process(data_i)
        1 0 1 1   0    1 1   process(data_i)
        -------   -    - -
        1 1 0 0   0    1 1   process(data_i)
        1 1 0 1   1    1 0   reg (odata, unchanged)
        1 1 1 0   0    1 1   process(data_i)
        1 1 1 1   0    1 1   process(data_i)
        -------   -    - -

        Note: PoR is *NOT* involved in the above decision-making.
    """

    def elaborate(self, platform):
        self.m = m = ControlBase.elaborate(self, platform)

        buf_full = Signal() # is data valid or not
        buf = _spec(self.stage.ospec, "r_tmp") # output type

        # some temporaries
        p_valid_i = Signal(reset_less=True)
        m.d.comb += p_valid_i.eq(self.p.valid_i_test)

        m.d.comb += self.n.valid_o.eq(buf_full | p_valid_i)
        m.d.comb += self.p._ready_o.eq(~buf_full)
        m.d.sync += buf_full.eq(~self.n.ready_i_test & self.n.valid_o)

        data_o = Mux(buf_full, buf, self.data_r)
        data_o = self._postprocess(data_o) # XXX TBD, does nothing right now
        m.d.comb += nmoperator.eq(self.n.data_o, data_o)
        m.d.sync += nmoperator.eq(buf, self.n.data_o)

        return self.m


class PassThroughHandshake(ControlBase):
    """ A control block that delays by one clock cycle.

        Inputs   Temporary          Output Data
        -------  ------------------  ----- ----
        P P N N  PiV& PiV| NiR| pvr   N P  (pvr)
        i o i o  PoR  ~PoR ~NoV       o o
        V R R V                       V R

        -------   -    -    -   -     - -
        0 0 0 0   0    1    1   0     1 1   odata (unchanged)
        0 0 0 1   0    1    0   0     1 0   odata (unchanged)
        0 0 1 0   0    1    1   0     1 1   odata (unchanged)
        0 0 1 1   0    1    1   0     1 1   odata (unchanged)
        -------   -    -    -   -     - -
        0 1 0 0   0    0    1   0     0 1   odata (unchanged)
        0 1 0 1   0    0    0   0     0 0   odata (unchanged)
        0 1 1 0   0    0    1   0     0 1   odata (unchanged)
        0 1 1 1   0    0    1   0     0 1   odata (unchanged)
        -------   -    -    -   -     - -
        1 0 0 0   0    1    1   1     1 1   process(in)
        1 0 0 1   0    1    0   0     1 0   odata (unchanged)
        1 0 1 0   0    1    1   1     1 1   process(in)
        1 0 1 1   0    1    1   1     1 1   process(in)
        -------   -    -    -   -     - -
        1 1 0 0   1    1    1   1     1 1   process(in)
        1 1 0 1   1    1    0   0     1 0   odata (unchanged)
        1 1 1 0   1    1    1   1     1 1   process(in)
        1 1 1 1   1    1    1   1     1 1   process(in)
        -------   -    -    -   -     - -

    """

    def elaborate(self, platform):
        self.m = m = ControlBase.elaborate(self, platform)

        r_data = _spec(self.stage.ospec, "r_tmp") # output type

        # temporaries
        p_valid_i = Signal(reset_less=True)
        pvr = Signal(reset_less=True)
        m.d.comb += p_valid_i.eq(self.p.valid_i_test)
        m.d.comb += pvr.eq(p_valid_i & self.p.ready_o)

        m.d.comb += self.p.ready_o.eq(~self.n.valid_o |  self.n.ready_i_test)
        m.d.sync += self.n.valid_o.eq(p_valid_i       | ~self.p.ready_o)

        odata = Mux(pvr, self.data_r, r_data)
        m.d.sync += nmoperator.eq(r_data, odata)
        r_data = self._postprocess(r_data) # XXX TBD, does nothing right now
        m.d.comb += nmoperator.eq(self.n.data_o, r_data)

        return m


class RegisterPipeline(UnbufferedPipeline):
    """ A pipeline stage that delays by one clock cycle, creating a
        sync'd latch out of data_o and valid_o as an indirect byproduct
        of using PassThroughStage
    """
    def __init__(self, iospecfn):
        UnbufferedPipeline.__init__(self, PassThroughStage(iospecfn))


class FIFOControl(ControlBase):
    """ FIFO Control.  Uses Queue to store data, coincidentally
        happens to have same valid/ready signalling as Stage API.

        data_i -> fifo.din -> FIFO -> fifo.dout -> data_o
    """
    def __init__(self, depth, stage, in_multi=None, stage_ctl=False,
                                     fwft=True, pipe=False):
        """ FIFO Control

            * :depth: number of entries in the FIFO
            * :stage: data processing block
            * :fwft:  first word fall-thru mode (non-fwft introduces delay)
            * :pipe:  specifies pipe mode.

            when fwft = True it indicates that transfers may occur
            combinatorially through stage processing in the same clock cycle.
            This requires that the Stage be a Moore FSM:
            https://en.wikipedia.org/wiki/Moore_machine

            when fwft = False it indicates that all output signals are
            produced only from internal registers or memory, i.e. that the
            Stage is a Mealy FSM:
            https://en.wikipedia.org/wiki/Mealy_machine

            data is processed (and located) as follows:

            self.p  self.stage temp    fn temp  fn  temp  fp   self.n
            data_i->process()->result->cat->din.FIFO.dout->cat(data_o)

            yes, really: cat produces a Cat() which can be assigned to.
            this is how the FIFO gets de-catted without needing a de-cat
            function
        """
        self.fwft = fwft
        self.pipe = pipe
        self.fdepth = depth
        ControlBase.__init__(self, stage, in_multi, stage_ctl)

    def elaborate(self, platform):
        self.m = m = ControlBase.elaborate(self, platform)

        # make a FIFO with a signal of equal width to the data_o.
        (fwidth, _) = nmoperator.shape(self.n.data_o)
        fifo = Queue(fwidth, self.fdepth, fwft=self.fwft, pipe=self.pipe)
        m.submodules.fifo = fifo

        def processfn(data_i):
            # store result of processing in combinatorial temporary
            result = _spec(self.stage.ospec, "r_temp")
            m.d.comb += nmoperator.eq(result, self.process(data_i))
            return nmoperator.cat(result)

        ## prev: make the FIFO (Queue object) "look" like a PrevControl...
        m.submodules.fp = fp = PrevControl()
        fp.valid_i, fp._ready_o, fp.data_i = fifo.we, fifo.writable, fifo.din
        m.d.comb += fp._connect_in(self.p, fn=processfn)

        # next: make the FIFO (Queue object) "look" like a NextControl...
        m.submodules.fn = fn = NextControl()
        fn.valid_o, fn.ready_i, fn.data_o  = fifo.readable, fifo.re, fifo.dout
        connections = fn._connect_out(self.n, fn=nmoperator.cat)

        # ok ok so we can't just do the ready/valid eqs straight:
        # first 2 from connections are the ready/valid, 3rd is data.
        if self.fwft:
            m.d.comb += connections[:2] # combinatorial on next ready/valid
        else:
            m.d.sync += connections[:2]  # non-fwft mode needs sync
        data_o = connections[2] # get the data
        data_o = self._postprocess(data_o) # XXX TBD, does nothing right now
        m.d.comb += data_o

        return m


# aka "RegStage".
class UnbufferedPipeline(FIFOControl):
    def __init__(self, stage, in_multi=None, stage_ctl=False):
        FIFOControl.__init__(self, 1, stage, in_multi, stage_ctl,
                                   fwft=True, pipe=False)

# aka "BreakReadyStage" XXX had to set fwft=True to get it to work
class PassThroughHandshake(FIFOControl):
    def __init__(self, stage, in_multi=None, stage_ctl=False):
        FIFOControl.__init__(self, 1, stage, in_multi, stage_ctl,
                                   fwft=True, pipe=True)

# this is *probably* BufferedHandshake, although test #997 now succeeds.
class BufferedHandshake(FIFOControl):
    def __init__(self, stage, in_multi=None, stage_ctl=False):
        FIFOControl.__init__(self, 2, stage, in_multi, stage_ctl,
                                   fwft=True, pipe=False)


"""
# this is *probably* SimpleHandshake (note: memory cell size=0)
class SimpleHandshake(FIFOControl):
    def __init__(self, stage, in_multi=None, stage_ctl=False):
        FIFOControl.__init__(self, 0, stage, in_multi, stage_ctl,
                                   fwft=True, pipe=False)
"""
