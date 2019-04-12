""" Pipeline and BufferedHandshake implementation, conforming to the same API.
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

    SimpleHandshake
    ---------------

    Synchronised pipeline, Based on:
    https://github.com/ZipCPU/dbgbus/blob/master/hexbus/rtl/hbdeword.v
"""

from nmigen import Signal, Cat, Const, Mux, Module, Value
from nmigen.cli import verilog, rtlil
from nmigen.lib.fifo import SyncFIFO
from nmigen.hdl.ast import ArrayProxy
from nmigen.hdl.rec import Record, Layout

from abc import ABCMeta, abstractmethod
from collections.abc import Sequence


class RecordObject(Record):
    def __init__(self, layout=None, name=None):
        Record.__init__(self, layout=layout or [], name=None)

    def __setattr__(self, k, v):
        if k in dir(Record) or "fields" not in self.__dict__:
            return object.__setattr__(self, k, v)
        self.fields[k] = v
        if isinstance(v, Record):
            newlayout = {k: (k, v.layout)}
        else:
            newlayout = {k: (k, v.shape())}
        self.layout.fields.update(newlayout)



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

    def _connect_in(self, prev, direct=False, fn=None):
        """ internal helper function to connect stage to an input source.
            do not use to connect stage-to-stage!
        """
        i_valid = prev.i_valid if direct else prev.i_valid_test
        i_data = fn(prev.i_data) if fn is not None else prev.i_data
        return [self.i_valid.eq(i_valid),
                prev.o_ready.eq(self.o_ready),
                eq(self.i_data, i_data),
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

    def _connect_out(self, nxt, direct=False, fn=None):
        """ internal helper function to connect stage to an output source.
            do not use to connect stage-to-stage!
        """
        i_ready = nxt.i_ready if direct else nxt.i_ready_test
        o_data = fn(nxt.o_data) if fn is not None else nxt.o_data
        return [nxt.o_valid.eq(self.o_valid),
                self.i_ready.eq(i_ready),
                eq(o_data, self.o_data),
               ]


class Visitor:
    """ a helper routine which identifies if it is being passed a list
        (or tuple) of objects, or signals, or Records, and calls
        a visitor function.

        the visiting fn is called when an object is identified.

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
    def visit(self, o, i, act):
        if isinstance(o, dict):
            return self.dict_visit(o, i, act)

        res = act.prepare()
        if not isinstance(o, Sequence):
            o, i = [o], [i]
        for (ao, ai) in zip(o, i):
            #print ("visit", fn, ao, ai)
            if isinstance(ao, Record):
                rres = self.record_visit(ao, ai, act)
            elif isinstance(ao, ArrayProxy) and not isinstance(ai, Value):
                rres = self.arrayproxy_visit(ao, ai, act)
            else:
                rres = act.fn(ao, ai)
            res += rres
        return res

    def dict_visit(self, o, i, act):
        res = act.prepare()
        for (k, v) in o.items():
            print ("d-eq", v, i[k])
            res.append(act.fn(v, i[k]))
        return res

    def record_visit(self, ao, ai, act):
        res = act.prepare()
        for idx, (field_name, field_shape, _) in enumerate(ao.layout):
            if isinstance(field_shape, Layout):
                val = ai.fields
            else:
                val = ai
            if hasattr(val, field_name): # check for attribute
                val = getattr(val, field_name)
            else:
                val = val[field_name] # dictionary-style specification
            val = self.visit(ao.fields[field_name], val, act)
            if isinstance(val, Sequence):
                res += val
            else:
                res.append(val)
        return res

    def arrayproxy_visit(self, ao, ai, act):
        res = act.prepare()
        for p in ai.ports():
            op = getattr(ao, p.name)
            #print (op, p, p.name)
            res.append(fn(op, p))
        return res


class Eq(Visitor):
    def __init__(self):
        self.res = []
    def prepare(self):
        return []
    def fn(self, o, i):
        rres = o.eq(i)
        if not isinstance(rres, Sequence):
            rres = [rres]
        return rres
    def __call__(self, o, i):
        return self.visit(o, i, self)


def eq(o, i):
    """ makes signals equal: a helper routine which identifies if it is being
        passed a list (or tuple) of objects, or signals, or Records, and calls
        the objects' eq function.
    """
    return Eq()(o, i)


def flatten(i):
    """ flattens a compound structure recursively using Cat
    """
    if not isinstance(i, Sequence):
        i = [i]
    res = []
    for ai in i:
        print ("flatten", ai)
        if isinstance(ai, Record):
            print ("record", list(ai.layout))
            rres = []
            for idx, (field_name, field_shape, _) in enumerate(ai.layout):
                if isinstance(field_shape, Layout):
                    val = ai.fields
                else:
                    val = ai
                if hasattr(val, field_name): # check for attribute
                    val = getattr(val, field_name)
                else:
                    val = val[field_name] # dictionary-style specification
                print ("recidx", idx, field_name, field_shape, val)
                val = flatten(val)
                print ("recidx flat", idx, val)
                if isinstance(val, Sequence):
                    rres += val
                else:
                    rres.append(val)

        elif isinstance(ai, ArrayProxy) and not isinstance(ai, Value):
            rres = []
            for p in ai.ports():
                op = getattr(ai, p.name)
                #print (op, p, p.name)
                rres.append(flatten(p))
        else:
            rres = ai
        if not isinstance(rres, Sequence):
            rres = [rres]
        res += rres
        print ("flatten res", res)
    return Cat(*res)



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

    def _specallocate_setup(self, m, i):
        for (idx, c) in enumerate(self.chain):
            if hasattr(c, "setup"):
                c.setup(m, i)               # stage may have some module stuff
            o = self.chain[idx].ospec()     # last assignment survives
            m.d.comb += eq(o, c.process(i)) # process input into "o"
            if idx == len(self.chain)-1:
                break
            i = self.chain[idx+1].ispec()   # new input on next loop
            m.d.comb += eq(i, o)            # assign to next input
        return o                            # last loop is the output

    def _noallocate_setup(self, m, i):
        for (idx, c) in enumerate(self.chain):
            if hasattr(c, "setup"):
                c.setup(m, i)               # stage may have some module stuff
            i = o = c.process(i)            # store input into "o"
        return o                            # last loop is the output

    def setup(self, m, i):
        if self.specallocate:
            self.o = self._specallocate_setup(m, i)
        else:
            self.o = self._noallocate_setup(m, i)

    def process(self, i):
        return self.o # conform to Stage API: return last-loop output


class ControlBase:
    """ Common functions for Pipeline API
    """
    def __init__(self, stage=None, in_multi=None, stage_ctl=False):
        """ Base class containing ready/valid/data to previous and next stages

            * p: contains ready/valid to the previous stage
            * n: contains ready/valid to the next stage

            Except when calling Controlbase.connect(), user must also:
            * add i_data member to PrevControl (p) and
            * add o_data member to NextControl (n)
        """
        self.stage = stage

        # set up input and output IO ACK (prev/next ready/valid)
        self.p = PrevControl(in_multi, stage_ctl)
        self.n = NextControl(stage_ctl)

        # set up the input and output data
        if stage is not None:
            self.p.i_data = stage.ispec() # input type
            self.n.o_data = stage.ospec()

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

        if self.stage is not None and hasattr(self.stage, "setup"):
            self.stage.setup(m, self.p.i_data)

        if not self.p.stage_ctl:
            return m

        # intercept the previous (outgoing) "ready", combine with stage ready
        m.d.comb += self.p.s_o_ready.eq(self.p._o_ready & self.stage.d_ready)

        # intercept the next (incoming) "ready" and combine it with data valid
        sdv = self.stage.d_valid(self.n.i_ready)
        m.d.comb += self.n.d_valid.eq(self.n.i_ready & sdv)

        return m


class BufferedHandshake(ControlBase):
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

    def elaborate(self, platform):
        self.m = ControlBase._elaborate(self, platform)

        result = self.stage.ospec()
        r_data = self.stage.ospec()

        # establish some combinatorial temporaries
        o_n_validn = Signal(reset_less=True)
        n_i_ready = Signal(reset_less=True, name="n_i_rdy_data")
        nir_por = Signal(reset_less=True)
        nir_por_n = Signal(reset_less=True)
        p_i_valid = Signal(reset_less=True)
        nir_novn = Signal(reset_less=True)
        nirn_novn = Signal(reset_less=True)
        por_pivn = Signal(reset_less=True)
        npnn = Signal(reset_less=True)
        self.m.d.comb += [p_i_valid.eq(self.p.i_valid_test),
                     o_n_validn.eq(~self.n.o_valid),
                     n_i_ready.eq(self.n.i_ready_test),
                     nir_por.eq(n_i_ready & self.p._o_ready),
                     nir_por_n.eq(n_i_ready & ~self.p._o_ready),
                     nir_novn.eq(n_i_ready | o_n_validn),
                     nirn_novn.eq(~n_i_ready & o_n_validn),
                     npnn.eq(nir_por | nirn_novn),
                     por_pivn.eq(self.p._o_ready & ~p_i_valid)
        ]

        # store result of processing in combinatorial temporary
        self.m.d.comb += eq(result, self.stage.process(self.p.i_data))

        # if not in stall condition, update the temporary register
        with self.m.If(self.p.o_ready): # not stalled
            self.m.d.sync += eq(r_data, result) # update buffer

        # data pass-through conditions
        with self.m.If(npnn):
            self.m.d.sync += [self.n.o_valid.eq(p_i_valid), # valid if p_valid
                              eq(self.n.o_data, result),    # update output
                             ]
        # buffer flush conditions (NOTE: can override data passthru conditions)
        with self.m.If(nir_por_n): # not stalled
            # Flush the [already processed] buffer to the output port.
            self.m.d.sync += [self.n.o_valid.eq(1),  # reg empty
                              eq(self.n.o_data, r_data), # flush buffer
                             ]
        # output ready conditions
        self.m.d.sync += self.p._o_ready.eq(nir_novn | por_pivn)

        return self.m


class SimpleHandshake(ControlBase):
    """ simple handshake control.  data and strobe signals travel in sync.
        implements the protocol used by Wishbone and AXI4.

        Argument: stage.  see Stage API above

        stage-1   p.i_valid >>in   stage   n.o_valid out>>   stage+1
        stage-1   p.o_ready <<out  stage   n.i_ready <<in    stage+1
        stage-1   p.i_data  >>in   stage   n.o_data  out>>   stage+1
                              |             |
                              +--process->--^
        Truth Table

        Inputs   Temporary  Output
        -------  ---------- -----
        P P N N  PiV& ~NiV&  N P
        i o i o  PoR  NoV    o o
        V R R V              V R

        -------   -    -     - -
        0 0 0 0   0    0    >0 0
        0 0 0 1   0    1    >1 0
        0 0 1 0   0    0     0 1
        0 0 1 1   0    0     0 1
        -------   -    -     - -
        0 1 0 0   0    0    >0 0
        0 1 0 1   0    1    >1 0
        0 1 1 0   0    0     0 1
        0 1 1 1   0    0     0 1
        -------   -    -     - -
        1 0 0 0   0    0    >0 0
        1 0 0 1   0    1    >1 0
        1 0 1 0   0    0     0 1
        1 0 1 1   0    0     0 1
        -------   -    -     - -
        1 1 0 0   1    0     1 0
        1 1 0 1   1    1     1 0
        1 1 1 0   1    0     1 1
        1 1 1 1   1    0     1 1
        -------   -    -     - -
    """

    def elaborate(self, platform):
        self.m = m = ControlBase._elaborate(self, platform)

        r_busy = Signal()
        result = self.stage.ospec()

        # establish some combinatorial temporaries
        n_i_ready = Signal(reset_less=True, name="n_i_rdy_data")
        p_i_valid_p_o_ready = Signal(reset_less=True)
        p_i_valid = Signal(reset_less=True)
        m.d.comb += [p_i_valid.eq(self.p.i_valid_test),
                     n_i_ready.eq(self.n.i_ready_test),
                     p_i_valid_p_o_ready.eq(p_i_valid & self.p.o_ready),
        ]

        # store result of processing in combinatorial temporary
        m.d.comb += eq(result, self.stage.process(self.p.i_data))

        # previous valid and ready
        with m.If(p_i_valid_p_o_ready):
            m.d.sync += [r_busy.eq(1),      # output valid
                         eq(self.n.o_data, result), # update output
                        ]
        # previous invalid or not ready, however next is accepting
        with m.Elif(n_i_ready):
            m.d.sync += [eq(self.n.o_data, result)]
            # TODO: could still send data here (if there was any)
            #m.d.sync += self.n.o_valid.eq(0) # ...so set output invalid
            m.d.sync += r_busy.eq(0) # ...so set output invalid

        m.d.comb += self.n.o_valid.eq(r_busy)
        # if next is ready, so is previous
        m.d.comb += self.p._o_ready.eq(n_i_ready)

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

        Truth Table

        Inputs  Temp  Output
        -------   -   -----
        P P N N ~NiR&  N P
        i o i o  NoV   o o
        V R R V        V R

        -------   -    - -
        0 0 0 0   0    0 1
        0 0 0 1   1    1 0
        0 0 1 0   0    0 1
        0 0 1 1   0    0 1
        -------   -    - -
        0 1 0 0   0    0 1
        0 1 0 1   1    1 0
        0 1 1 0   0    0 1
        0 1 1 1   0    0 1
        -------   -    - -
        1 0 0 0   0    1 1
        1 0 0 1   1    1 0
        1 0 1 0   0    1 1
        1 0 1 1   0    1 1
        -------   -    - -
        1 1 0 0   0    1 1
        1 1 0 1   1    1 0
        1 1 1 0   0    1 1
        1 1 1 1   0    1 1
        -------   -    - -

        Note: PoR is *NOT* involved in the above decision-making.
    """

    def elaborate(self, platform):
        self.m = m = ControlBase._elaborate(self, platform)

        data_valid = Signal() # is data valid or not
        r_data = self.stage.ospec() # output type

        # some temporaries
        p_i_valid = Signal(reset_less=True)
        pv = Signal(reset_less=True)
        m.d.comb += p_i_valid.eq(self.p.i_valid_test)
        m.d.comb += pv.eq(self.p.i_valid & self.p.o_ready)

        m.d.comb += self.n.o_valid.eq(data_valid)
        m.d.comb += self.p._o_ready.eq(~data_valid | self.n.i_ready_test)
        m.d.sync += data_valid.eq(p_i_valid | \
                                        (~self.n.i_ready_test & data_valid))
        with m.If(pv):
            m.d.sync += eq(r_data, self.stage.process(self.p.i_data))
        m.d.comb += eq(self.n.o_data, r_data)

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

        stage-1   p.i_valid >>in   stage   n.o_valid out>>   stage+1
        stage-1   p.o_ready <<out  stage   n.i_ready <<in    stage+1
        stage-1   p.i_data  >>in   stage   n.o_data  out>>   stage+1
                              |             |    |
                              +- process-> buf <-+
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

    def elaborate(self, platform):
        self.m = m = ControlBase._elaborate(self, platform)

        buf_full = Signal() # is data valid or not
        buf = self.stage.ospec() # output type

        # some temporaries
        p_i_valid = Signal(reset_less=True)
        m.d.comb += p_i_valid.eq(self.p.i_valid_test)

        m.d.comb += self.n.o_valid.eq(buf_full | p_i_valid)
        m.d.comb += self.p._o_ready.eq(~buf_full)
        m.d.sync += buf_full.eq(~self.n.i_ready_test & self.n.o_valid)

        odata = Mux(buf_full, buf, self.stage.process(self.p.i_data))
        m.d.comb += eq(self.n.o_data, odata)
        m.d.sync += eq(buf, self.n.o_data)

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
    """

    def elaborate(self, platform):
        self.m = m = ControlBase._elaborate(self, platform)

        # temporaries
        p_i_valid = Signal(reset_less=True)
        pvr = Signal(reset_less=True)
        m.d.comb += p_i_valid.eq(self.p.i_valid_test)
        m.d.comb += pvr.eq(p_i_valid & self.p.o_ready)

        m.d.comb += self.p.o_ready.eq(~self.n.o_valid |  self.n.i_ready_test)
        m.d.sync += self.n.o_valid.eq(p_i_valid       | ~self.p.o_ready)

        odata = Mux(pvr, self.stage.process(self.p.i_data), self.n.o_data)
        m.d.sync += eq(self.n.o_data, odata)

        return m


class RegisterPipeline(UnbufferedPipeline):
    """ A pipeline stage that delays by one clock cycle, creating a
        sync'd latch out of o_data and o_valid as an indirect byproduct
        of using PassThroughStage
    """
    def __init__(self, iospecfn):
        UnbufferedPipeline.__init__(self, PassThroughStage(iospecfn))


class FIFOControl(ControlBase):
    """ FIFO Control.  Uses SyncFIFO to store data, coincidentally
        happens to have same valid/ready signalling as Stage API.

        i_data -> fifo.din -> FIFO -> fifo.dout -> o_data
    """

    def __init__(self, iospecfn, depth):
        """ * iospecfn: specification for incoming and outgoing data
            * depth   : number of entries in the FIFO

            NOTE: FPGAs may have trouble with the defaults for SyncFIFO
        """

        self.fdepth = depth
        stage = PassThroughStage(iospecfn)
        ControlBase.__init__(self, stage=stage)

    def elaborate(self, platform):
        self.m = m = ControlBase._elaborate(self, platform)

        (fwidth, _) = self.p.i_data.shape()
        fifo = SyncFIFO(fwidth, self.fdepth)
        m.submodules.fifo = fifo

        # prev: make the FIFO "look" like a PrevControl...
        fp = PrevControl()
        fp.i_valid = fifo.we
        fp._o_ready = fifo.writable
        fp.i_data = fifo.din
        m.d.comb += fp._connect_in(self.p, True, fn=flatten)

        # next: make the FIFO "look" like a NextControl...
        fn = NextControl()
        fn.o_valid = fifo.readable
        fn.i_ready = fifo.re
        fn.o_data = fifo.dout
        # ... so we can do this!
        m.d.comb += fn._connect_out(self.n, fn=flatten)

        # err... that should be all!
        return m

