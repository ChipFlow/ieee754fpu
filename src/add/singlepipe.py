""" Pipeline and BufferedHandshake implementation, conforming to the same API.
    For multi-input and multi-output variants, see multipipe.

    Associated development bugs:
    * http://bugs.libre-riscv.org/show_bug.cgi?id=64
    * http://bugs.libre-riscv.org/show_bug.cgi?id=57

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


class Object:
    def __init__(self):
        self.fields = OrderedDict()

    def __setattr__(self, k, v):
        print ("kv", k, v)
        if (k.startswith('_') or k in ["fields", "name", "src_loc"] or
           k in dir(Object) or "fields" not in self.__dict__):
            return object.__setattr__(self, k, v)
        self.fields[k] = v

    def __getattr__(self, k):
        if k in self.__dict__:
            return object.__getattr__(self, k)
        try:
            return self.fields[k]
        except KeyError as e:
            raise AttributeError(e)

    def __iter__(self):
        for x in self.fields.values():
            if isinstance(x, Iterable):
                yield from x
            else:
                yield x

    def eq(self, inp):
        res = []
        for (k, o) in self.fields.items():
            i = getattr(inp, k)
            print ("eq", o, i)
            rres = o.eq(i)
            if isinstance(rres, Sequence):
                res += rres
            else:
                res.append(rres)
        print (res)
        return res

    def ports(self):
        return list(self)


class RecordObject(Record):
    def __init__(self, layout=None, name=None):
        Record.__init__(self, layout=layout or [], name=None)

    def __setattr__(self, k, v):
        #print (dir(Record))
        if (k.startswith('_') or k in ["fields", "name", "src_loc"] or
           k in dir(Record) or "fields" not in self.__dict__):
            return object.__setattr__(self, k, v)
        self.fields[k] = v
        #print ("RecordObject setattr", k, v)
        if isinstance(v, Record):
            newlayout = {k: (k, v.layout)}
        elif isinstance(v, Value):
            newlayout = {k: (k, v.shape())}
        else:
            newlayout = {k: (k, shape(v))}
        self.layout.fields.update(newlayout)

    def __iter__(self):
        for x in self.fields.values():
            if isinstance(x, Iterable):
                yield from x
            else:
                yield x

    def ports(self):
        return list(self)


def _spec(fn, name=None):
    if name is None:
        return fn()
    varnames = dict(inspect.getmembers(fn.__code__))['co_varnames']
    if 'name' in varnames:
        return fn(name=name)
    return fn()


class PrevControl(Elaboratable):
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
        self.trigger = Signal(reset_less=True)

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

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.trigger.eq(self.i_valid_test & self.o_ready)
        return m

    def eq(self, i):
        return [self.i_data.eq(i.i_data),
                self.o_ready.eq(i.o_ready),
                self.i_valid.eq(i.i_valid)]

    def __iter__(self):
        yield self.i_valid
        yield self.o_ready
        if hasattr(self.i_data, "ports"):
            yield from self.i_data.ports()
        elif isinstance(self.i_data, Sequence):
            yield from self.i_data
        else:
            yield self.i_data

    def ports(self):
        return list(self)


class NextControl(Elaboratable):
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
        self.trigger = Signal(reset_less=True)

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

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.trigger.eq(self.i_ready_test & self.o_valid)
        return m

    def __iter__(self):
        yield self.i_ready
        yield self.o_valid
        if hasattr(self.o_data, "ports"):
            yield from self.o_data.ports()
        elif isinstance(self.o_data, Sequence):
            yield from self.o_data
        else:
            yield self.o_data

    def ports(self):
        return list(self)


class Visitor2:
    """ a helper class for iterating twin-argument compound data structures.

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
    def iterator2(self, o, i):
        if isinstance(o, dict):
            yield from self.dict_iter2(o, i)

        if not isinstance(o, Sequence):
            o, i = [o], [i]
        for (ao, ai) in zip(o, i):
            #print ("visit", fn, ao, ai)
            if isinstance(ao, Record):
                yield from self.record_iter2(ao, ai)
            elif isinstance(ao, ArrayProxy) and not isinstance(ai, Value):
                yield from self.arrayproxy_iter2(ao, ai)
            else:
                yield (ao, ai)

    def dict_iter2(self, o, i):
        for (k, v) in o.items():
            print ("d-iter", v, i[k])
            yield (v, i[k])
        return res

    def _not_quite_working_with_all_unit_tests_record_iter2(self, ao, ai):
        print ("record_iter2", ao, ai, type(ao), type(ai))
        if isinstance(ai, Value):
            if isinstance(ao, Sequence):
                ao, ai = [ao], [ai]
            for o, i in zip(ao, ai):
                yield (o, i)
            return
        for idx, (field_name, field_shape, _) in enumerate(ao.layout):
            if isinstance(field_shape, Layout):
                val = ai.fields
            else:
                val = ai
            if hasattr(val, field_name): # check for attribute
                val = getattr(val, field_name)
            else:
                val = val[field_name] # dictionary-style specification
            yield from self.iterator2(ao.fields[field_name], val)

    def record_iter2(self, ao, ai):
        for idx, (field_name, field_shape, _) in enumerate(ao.layout):
            if isinstance(field_shape, Layout):
                val = ai.fields
            else:
                val = ai
            if hasattr(val, field_name): # check for attribute
                val = getattr(val, field_name)
            else:
                val = val[field_name] # dictionary-style specification
            yield from self.iterator2(ao.fields[field_name], val)

    def arrayproxy_iter2(self, ao, ai):
        for p in ai.ports():
            op = getattr(ao, p.name)
            print ("arrayproxy - p", p, p.name)
            yield from self.iterator2(op, p)


class Visitor:
    """ a helper class for iterating single-argument compound data structures.
        similar to Visitor2.
    """
    def iterate(self, i):
        """ iterate a compound structure recursively using yield
        """
        if not isinstance(i, Sequence):
            i = [i]
        for ai in i:
            #print ("iterate", ai)
            if isinstance(ai, Record):
                #print ("record", list(ai.layout))
                yield from self.record_iter(ai)
            elif isinstance(ai, ArrayProxy) and not isinstance(ai, Value):
                yield from self.array_iter(ai)
            else:
                yield ai

    def record_iter(self, ai):
        for idx, (field_name, field_shape, _) in enumerate(ai.layout):
            if isinstance(field_shape, Layout):
                val = ai.fields
            else:
                val = ai
            if hasattr(val, field_name): # check for attribute
                val = getattr(val, field_name)
            else:
                val = val[field_name] # dictionary-style specification
            #print ("recidx", idx, field_name, field_shape, val)
            yield from self.iterate(val)

    def array_iter(self, ai):
        for p in ai.ports():
            yield from self.iterate(p)


def eq(o, i):
    """ makes signals equal: a helper routine which identifies if it is being
        passed a list (or tuple) of objects, or signals, or Records, and calls
        the objects' eq function.
    """
    res = []
    for (ao, ai) in Visitor2().iterator2(o, i):
        rres = ao.eq(ai)
        if not isinstance(rres, Sequence):
            rres = [rres]
        res += rres
    return res


def shape(i):
    #print ("shape", i)
    r = 0
    for part in list(i):
        #print ("shape?", part)
        s, _ = part.shape()
        r += s
    return r, False


def cat(i):
    """ flattens a compound structure recursively using Cat
    """
    from nmigen.tools import flatten
    #res = list(flatten(i)) # works (as of nmigen commit f22106e5) HOWEVER...
    res = list(Visitor().iterate(i)) # needed because input may be a sequence
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
        return _spec(self.chain[0].ispec, "chainin")

    def ospec(self):
        return _spec(self.chain[-1].ospec, "chainout")

    def _specallocate_setup(self, m, i):
        for (idx, c) in enumerate(self.chain):
            if hasattr(c, "setup"):
                c.setup(m, i)               # stage may have some module stuff
            ofn = self.chain[idx].ospec     # last assignment survives
            o = _spec(ofn, 'chainin%d' % idx)
            m.d.comb += eq(o, c.process(i)) # process input into "o"
            if idx == len(self.chain)-1:
                break
            i = self.chain[idx+1].ispec     # new input on next loop
            i = _spec(ifn, 'chainin%d' % idx+1)
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


class ControlBase(Elaboratable):
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
            self.p.i_data = _spec(stage.ispec, "i_data") # input type
            self.n.o_data = _spec(stage.ospec, "o_data") # output type

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
        self.p.i_data = _spec(front.stage.ispec, "chainin")
        eqs += front._connect_in(self)

        # connect end of chain to ourselves
        end = pipechain[-1]
        self.n.o_data = _spec(end.stage.ospec, "chainout")
        eqs += end._connect_out(self)

        return eqs

    def _postprocess(self, i): # XXX DISABLED
        return i # RETURNS INPUT
        if hasattr(self.stage, "postprocess"):
            return self.stage.postprocess(i)
        return i

    def set_input(self, i):
        """ helper function to set the input data
        """
        return eq(self.p.i_data, i)

    def __iter__(self):
        yield from self.p
        yield from self.n

    def ports(self):
        return list(self)

    def elaborate(self, platform):
        """ handles case where stage has dynamic ready/valid functions
        """
        m = Module()
        m.submodules.p = self.p
        m.submodules.n = self.n

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
        self.m = ControlBase.elaborate(self, platform)

        result = _spec(self.stage.ospec, "r_tmp")
        r_data = _spec(self.stage.ospec, "r_data")

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
            o_data = self._postprocess(result)
            self.m.d.sync += [self.n.o_valid.eq(p_i_valid), # valid if p_valid
                              eq(self.n.o_data, o_data),    # update output
                             ]
        # buffer flush conditions (NOTE: can override data passthru conditions)
        with self.m.If(nir_por_n): # not stalled
            # Flush the [already processed] buffer to the output port.
            o_data = self._postprocess(r_data)
            self.m.d.sync += [self.n.o_valid.eq(1),  # reg empty
                              eq(self.n.o_data, o_data), # flush buffer
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

        Inputs   Temporary  Output Data
        -------  ---------- -----  ----
        P P N N  PiV& ~NiR&  N P
        i o i o  PoR  NoV    o o
        V R R V              V R

        -------   -    -     - -
        0 0 0 0   0    0    >0 0    reg
        0 0 0 1   0    1    >1 0    reg
        0 0 1 0   0    0     0 1    process(i_data)
        0 0 1 1   0    0     0 1    process(i_data)
        -------   -    -     - -
        0 1 0 0   0    0    >0 0    reg
        0 1 0 1   0    1    >1 0    reg
        0 1 1 0   0    0     0 1    process(i_data)
        0 1 1 1   0    0     0 1    process(i_data)
        -------   -    -     - -
        1 0 0 0   0    0    >0 0    reg
        1 0 0 1   0    1    >1 0    reg
        1 0 1 0   0    0     0 1    process(i_data)
        1 0 1 1   0    0     0 1    process(i_data)
        -------   -    -     - -
        1 1 0 0   1    0     1 0    process(i_data)
        1 1 0 1   1    1     1 0    process(i_data)
        1 1 1 0   1    0     1 1    process(i_data)
        1 1 1 1   1    0     1 1    process(i_data)
        -------   -    -     - -
    """

    def elaborate(self, platform):
        self.m = m = ControlBase.elaborate(self, platform)

        r_busy = Signal()
        result = _spec(self.stage.ospec, "r_tmp")

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
            o_data = self._postprocess(result)
            m.d.sync += [r_busy.eq(1),      # output valid
                         eq(self.n.o_data, o_data), # update output
                        ]
        # previous invalid or not ready, however next is accepting
        with m.Elif(n_i_ready):
            o_data = self._postprocess(result)
            m.d.sync += [eq(self.n.o_data, o_data)]
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
        1 1 0 0   0    1 1    process(i_data)
        1 1 0 1   1    1 0    process(i_data)
        1 1 1 0   0    1 1    process(i_data)
        1 1 1 1   0    1 1    process(i_data)
        -------   -    - -

        Note: PoR is *NOT* involved in the above decision-making.
    """

    def elaborate(self, platform):
        self.m = m = ControlBase.elaborate(self, platform)

        data_valid = Signal() # is data valid or not
        r_data = _spec(self.stage.ospec, "r_tmp") # output type

        # some temporaries
        p_i_valid = Signal(reset_less=True)
        pv = Signal(reset_less=True)
        buf_full = Signal(reset_less=True)
        m.d.comb += p_i_valid.eq(self.p.i_valid_test)
        m.d.comb += pv.eq(self.p.i_valid & self.p.o_ready)
        m.d.comb += buf_full.eq(~self.n.i_ready_test & data_valid)

        m.d.comb += self.n.o_valid.eq(data_valid)
        m.d.comb += self.p._o_ready.eq(~data_valid | self.n.i_ready_test)
        m.d.sync += data_valid.eq(p_i_valid | buf_full)

        with m.If(pv):
            m.d.sync += eq(r_data, self.stage.process(self.p.i_data))
        o_data = self._postprocess(r_data)
        m.d.comb += eq(self.n.o_data, o_data)

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

        Inputs  Temp  Output Data
        -------   -   -----
        P P N N ~NiR&  N P   (buf_full)
        i o i o  NoV   o o
        V R R V        V R

        -------   -    - -
        0 0 0 0   0    0 1   process(i_data)
        0 0 0 1   1    1 0   reg (odata, unchanged)
        0 0 1 0   0    0 1   process(i_data)
        0 0 1 1   0    0 1   process(i_data)
        -------   -    - -
        0 1 0 0   0    0 1   process(i_data)
        0 1 0 1   1    1 0   reg (odata, unchanged)
        0 1 1 0   0    0 1   process(i_data)
        0 1 1 1   0    0 1   process(i_data)
        -------   -    - -
        1 0 0 0   0    1 1   process(i_data)
        1 0 0 1   1    1 0   reg (odata, unchanged)
        1 0 1 0   0    1 1   process(i_data)
        1 0 1 1   0    1 1   process(i_data)
        -------   -    - -
        1 1 0 0   0    1 1   process(i_data)
        1 1 0 1   1    1 0   reg (odata, unchanged)
        1 1 1 0   0    1 1   process(i_data)
        1 1 1 1   0    1 1   process(i_data)
        -------   -    - -

        Note: PoR is *NOT* involved in the above decision-making.
    """

    def elaborate(self, platform):
        self.m = m = ControlBase.elaborate(self, platform)

        buf_full = Signal() # is data valid or not
        buf = _spec(self.stage.ospec, "r_tmp") # output type

        # some temporaries
        p_i_valid = Signal(reset_less=True)
        m.d.comb += p_i_valid.eq(self.p.i_valid_test)

        m.d.comb += self.n.o_valid.eq(buf_full | p_i_valid)
        m.d.comb += self.p._o_ready.eq(~buf_full)
        m.d.sync += buf_full.eq(~self.n.i_ready_test & self.n.o_valid)

        o_data = Mux(buf_full, buf, self.stage.process(self.p.i_data))
        o_data = self._postprocess(o_data)
        m.d.comb += eq(self.n.o_data, o_data)
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
        p_i_valid = Signal(reset_less=True)
        pvr = Signal(reset_less=True)
        m.d.comb += p_i_valid.eq(self.p.i_valid_test)
        m.d.comb += pvr.eq(p_i_valid & self.p.o_ready)

        m.d.comb += self.p.o_ready.eq(~self.n.o_valid |  self.n.i_ready_test)
        m.d.sync += self.n.o_valid.eq(p_i_valid       | ~self.p.o_ready)

        odata = Mux(pvr, self.stage.process(self.p.i_data), r_data)
        m.d.sync += eq(r_data, odata)
        r_data = self._postprocess(r_data)
        m.d.comb += eq(self.n.o_data, r_data)

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

    def __init__(self, depth, stage, in_multi=None, stage_ctl=False,
                                     fwft=True, buffered=False, pipe=False):
        """ FIFO Control

            * depth: number of entries in the FIFO
            * stage: data processing block
            * fwft : first word fall-thru mode (non-fwft introduces delay)
            * buffered: use buffered FIFO (introduces extra cycle delay)

            NOTE 1: FPGAs may have trouble with the defaults for SyncFIFO
                    (fwft=True, buffered=False)

            NOTE 2: i_data *must* have a shape function.  it can therefore
                    be a Signal, or a Record, or a RecordObject.

            data is processed (and located) as follows:

            self.p  self.stage temp    fn temp  fn  temp  fp   self.n
            i_data->process()->result->cat->din.FIFO.dout->cat(o_data)

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

        # make a FIFO with a signal of equal width to the o_data.
        (fwidth, _) = shape(self.n.o_data)
        if self.buffered:
            fifo = SyncFIFOBuffered(fwidth, self.fdepth)
        else:
            fifo = Queue(fwidth, self.fdepth, fwft=self.fwft, pipe=self.pipe)
        m.submodules.fifo = fifo

        # store result of processing in combinatorial temporary
        result = _spec(self.stage.ospec, "r_temp")
        m.d.comb += eq(result, self.stage.process(self.p.i_data))

        # connect previous rdy/valid/data - do cat on i_data
        # NOTE: cannot do the PrevControl-looking trick because
        # of need to process the data.  shaaaame....
        m.d.comb += [fifo.we.eq(self.p.i_valid_test),
                     self.p.o_ready.eq(fifo.writable),
                     eq(fifo.din, cat(result)),
                   ]

        # connect next rdy/valid/data - do cat on o_data
        connections = [self.n.o_valid.eq(fifo.readable),
                     fifo.re.eq(self.n.i_ready_test),
                   ]
        if self.fwft or self.buffered:
            m.d.comb += connections
        else:
            m.d.sync += connections # unbuffered fwft mode needs sync
        o_data = cat(self.n.o_data).eq(fifo.dout)
        o_data = self._postprocess(o_data)
        m.d.comb += o_data

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
