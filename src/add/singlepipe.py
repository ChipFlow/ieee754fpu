""" Pipeline and BufferedHandshake implementation, conforming to the same API.
    For multi-input and multi-output variants, see multipipe.

    Associated development bugs:
    * http://bugs.libre-riscv.org/show_bug.cgi?id=64
    * http://bugs.libre-riscv.org/show_bug.cgi?id=57

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

from nmigen import Signal, Cat, Const, Mux, Module, Value, Elaboratable
from nmigen.cli import verilog, rtlil
from nmigen.lib.fifo import SyncFIFO, SyncFIFOBuffered
from nmigen.hdl.ast import ArrayProxy
from nmigen.hdl.rec import Record, Layout

from abc import ABCMeta, abstractmethod
from collections.abc import Sequence, Iterable
from collections import OrderedDict
from queue import Queue
import inspect

from nmoperator import eq, cat, shape
from iocontrol import (Object, RecordObject, _spec,
                       PrevControl, NextControl, StageCls, Stage,
                       ControlBase, StageChain)
                      

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
        self.m.d.comb += eq(result, self.stage.process(self.p.data_i))

        # if not in stall condition, update the temporary register
        with self.m.If(self.p.ready_o): # not stalled
            self.m.d.sync += eq(r_data, result) # update buffer

        # data pass-through conditions
        with self.m.If(npnn):
            data_o = self._postprocess(result)
            self.m.d.sync += [self.n.valid_o.eq(p_valid_i), # valid if p_valid
                              eq(self.n.data_o, data_o),    # update output
                             ]
        # buffer flush conditions (NOTE: can override data passthru conditions)
        with self.m.If(nir_por_n): # not stalled
            # Flush the [already processed] buffer to the output port.
            data_o = self._postprocess(r_data)
            self.m.d.sync += [self.n.valid_o.eq(1),  # reg empty
                              eq(self.n.data_o, data_o), # flush buffer
                             ]
        # output ready conditions
        self.m.d.sync += self.p._ready_o.eq(nir_novn | por_pivn)

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
        m.d.comb += eq(result, self.stage.process(self.p.data_i))

        # previous valid and ready
        with m.If(p_valid_i_p_ready_o):
            data_o = self._postprocess(result)
            m.d.sync += [r_busy.eq(1),      # output valid
                         eq(self.n.data_o, data_o), # update output
                        ]
        # previous invalid or not ready, however next is accepting
        with m.Elif(n_ready_i):
            data_o = self._postprocess(result)
            m.d.sync += [eq(self.n.data_o, data_o)]
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
            m.d.sync += eq(r_data, self.stage.process(self.p.data_i))
        data_o = self._postprocess(r_data)
        m.d.comb += eq(self.n.data_o, data_o)

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

        data_o = Mux(buf_full, buf, self.stage.process(self.p.data_i))
        data_o = self._postprocess(data_o)
        m.d.comb += eq(self.n.data_o, data_o)
        m.d.sync += eq(buf, self.n.data_o)

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

        odata = Mux(pvr, self.stage.process(self.p.data_i), r_data)
        m.d.sync += eq(r_data, odata)
        r_data = self._postprocess(r_data)
        m.d.comb += eq(self.n.data_o, r_data)

        return m


class RegisterPipeline(UnbufferedPipeline):
    """ A pipeline stage that delays by one clock cycle, creating a
        sync'd latch out of data_o and valid_o as an indirect byproduct
        of using PassThroughStage
    """
    def __init__(self, iospecfn):
        UnbufferedPipeline.__init__(self, PassThroughStage(iospecfn))


class FIFOControl(ControlBase):
    """ FIFO Control.  Uses SyncFIFO to store data, coincidentally
        happens to have same valid/ready signalling as Stage API.

        data_i -> fifo.din -> FIFO -> fifo.dout -> data_o
    """

    def __init__(self, depth, stage, in_multi=None, stage_ctl=False,
                                     fwft=True, buffered=False, pipe=False):
        """ FIFO Control

            * depth: number of entries in the FIFO
            * stage: data processing block
            * fwft : first word fall-thru mode (non-fwft introduces delay)
            * buffered: use buffered FIFO (introduces extra cycle delay)

            NOTE 1: FPGAs may have trouble with the defaults for SyncFIFO
                    (fwft=True, buffered=False)

            NOTE 2: data_i *must* have a shape function.  it can therefore
                    be a Signal, or a Record, or a RecordObject.

            data is processed (and located) as follows:

            self.p  self.stage temp    fn temp  fn  temp  fp   self.n
            data_i->process()->result->cat->din.FIFO.dout->cat(data_o)

            yes, really: cat produces a Cat() which can be assigned to.
            this is how the FIFO gets de-catted without needing a de-cat
            function
        """

        assert not (fwft and buffered), "buffered cannot do fwft"
        if buffered:
            depth += 1
        self.fwft = fwft
        self.buffered = buffered
        self.pipe = pipe
        self.fdepth = depth
        ControlBase.__init__(self, stage, in_multi, stage_ctl)

    def elaborate(self, platform):
        self.m = m = ControlBase.elaborate(self, platform)

        # make a FIFO with a signal of equal width to the data_o.
        (fwidth, _) = shape(self.n.data_o)
        if self.buffered:
            fifo = SyncFIFOBuffered(fwidth, self.fdepth)
        else:
            fifo = Queue(fwidth, self.fdepth, fwft=self.fwft, pipe=self.pipe)
        m.submodules.fifo = fifo

        # store result of processing in combinatorial temporary
        result = _spec(self.stage.ospec, "r_temp")
        m.d.comb += eq(result, self.stage.process(self.p.data_i))

        # connect previous rdy/valid/data - do cat on data_i
        # NOTE: cannot do the PrevControl-looking trick because
        # of need to process the data.  shaaaame....
        m.d.comb += [fifo.we.eq(self.p.valid_i_test),
                     self.p.ready_o.eq(fifo.writable),
                     eq(fifo.din, cat(result)),
                   ]

        # connect next rdy/valid/data - do cat on data_o
        connections = [self.n.valid_o.eq(fifo.readable),
                     fifo.re.eq(self.n.ready_i_test),
                   ]
        if self.fwft or self.buffered:
            m.d.comb += connections
        else:
            m.d.sync += connections # unbuffered fwft mode needs sync
        data_o = cat(self.n.data_o).eq(fifo.dout)
        data_o = self._postprocess(data_o)
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
