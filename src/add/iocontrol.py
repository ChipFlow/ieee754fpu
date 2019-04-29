""" IO Control API

    Associated development bugs:
    * http://bugs.libre-riscv.org/show_bug.cgi?id=64
    * http://bugs.libre-riscv.org/show_bug.cgi?id=57

    Stage API:
    ---------

    stage requires compliance with a strict API that may be
    implemented in several means, including as a static class.

    Stage Blocks really must be combinatorial blocks.  It would be ok
    to have input come in from sync'd sources (clock-driven) however by
    doing so they would no longer be deterministic, and chaining such
    blocks with such side-effects together could result in unexpected,
    unpredictable, unreproduceable behaviour.
    So generally to be avoided, then unless you know what you are doing.

    the methods of a stage instance must be as follows:

    * ispec() - Input data format specification.  Takes a bit of explaining.
                The requirements are: something that eventually derives from
                nmigen Value must be returned *OR* an iterator or iterable
                or sequence (list, tuple etc.) or generator must *yield*
                thing(s) that (eventually) derive from the nmigen Value
                class.  Complex to state, very simple in practice:
                see test_buf_pipe.py for over 25 working examples.

    * ospec() - Output data format specification.
                requirements identical to ispec

    * process(m, i) - Processes an ispec-formatted object/sequence
                returns a combinatorial block of a result that
                may be assigned to the output, by way of the "nmoperator.eq"
                function.  Note that what is returned here can be
                extremely flexible.  Even a dictionary can be returned
                as long as it has fields that match precisely with the
                Record into which its values is intended to be assigned.
                Again: see example unit tests for details.

    * setup(m, i) - Optional function for setting up submodules
                may be used for more complex stages, to link
                the input (i) to submodules.  must take responsibility
                for adding those submodules to the module (m).
                the submodules must be combinatorial blocks and
                must have their inputs and output linked combinatorially.

    Both StageCls (for use with non-static classes) and Stage (for use
    by static classes) are abstract classes from which, for convenience
    and as a courtesy to other developers, anything conforming to the
    Stage API may *choose* to derive.  See Liskov Substitution Principle:
    https://en.wikipedia.org/wiki/Liskov_substitution_principle

    StageChain:
    ----------

    A useful combinatorial wrapper around stages that chains them together
    and then presents a Stage-API-conformant interface.  By presenting
    the same API as the stages it wraps, it can clearly be used recursively.

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
"""

from nmigen import Signal, Cat, Const, Mux, Module, Value, Elaboratable
from nmigen.cli import verilog, rtlil
from nmigen.hdl.rec import Record

from abc import ABCMeta, abstractmethod
from collections.abc import Sequence, Iterable
from collections import OrderedDict
import inspect

import nmoperator


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
        for x in self.fields.values():  # OrderedDict so order is preserved
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

    def ports(self): # being called "keys" would be much better
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
            newlayout = {k: (k, nmoperator.shape(v))}
        self.layout.fields.update(newlayout)

    def __iter__(self):
        for x in self.fields.values(): # remember: fields is an OrderedDict
            if isinstance(x, Iterable):
                yield from x           # a bit like flatten (nmigen.tools)
            else:
                yield x

    def ports(self): # would be better being called "keys"
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
        * valid_i: previous stage indicating all incoming data is valid.
                   may be a multi-bit signal, where all bits are required
                   to be asserted to indicate "valid".
        * ready_o: output to next stage indicating readiness to accept data
        * data_i : an input - MUST be added by the USER of this class
    """

    def __init__(self, i_width=1, stage_ctl=False):
        self.stage_ctl = stage_ctl
        self.valid_i = Signal(i_width, name="p_valid_i") # prev   >>in  self
        self._ready_o = Signal(name="p_ready_o")         # prev   <<out self
        self.data_i = None # XXX MUST BE ADDED BY USER
        if stage_ctl:
            self.s_ready_o = Signal(name="p_s_o_rdy")    # prev   <<out self
        self.trigger = Signal(reset_less=True)

    @property
    def ready_o(self):
        """ public-facing API: indicates (externally) that stage is ready
        """
        if self.stage_ctl:
            return self.s_ready_o # set dynamically by stage
        return self._ready_o      # return this when not under dynamic control

    def _connect_in(self, prev, direct=False, fn=None):
        """ internal helper function to connect stage to an input source.
            do not use to connect stage-to-stage!
        """
        valid_i = prev.valid_i if direct else prev.valid_i_test
        data_i = fn(prev.data_i) if fn is not None else prev.data_i
        return [self.valid_i.eq(valid_i),
                prev.ready_o.eq(self.ready_o),
                nmoperator.eq(self.data_i, data_i),
               ]

    @property
    def valid_i_test(self):
        vlen = len(self.valid_i)
        if vlen > 1:
            # multi-bit case: valid only when valid_i is all 1s
            all1s = Const(-1, (len(self.valid_i), False))
            valid_i = (self.valid_i == all1s)
        else:
            # single-bit valid_i case
            valid_i = self.valid_i

        # when stage indicates not ready, incoming data
        # must "appear" to be not ready too
        if self.stage_ctl:
            valid_i = valid_i & self.s_ready_o

        return valid_i

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.trigger.eq(self.valid_i_test & self.ready_o)
        return m

    def eq(self, i):
        return [self.data_i.eq(i.data_i),
                self.ready_o.eq(i.ready_o),
                self.valid_i.eq(i.valid_i)]

    def __iter__(self):
        yield self.valid_i
        yield self.ready_o
        if hasattr(self.data_i, "ports"):
            yield from self.data_i.ports()
        elif isinstance(self.data_i, Sequence):
            yield from self.data_i
        else:
            yield self.data_i

    def ports(self):
        return list(self)


class NextControl(Elaboratable):
    """ contains the signals that go *to* the next stage (both in and out)
        * valid_o: output indicating to next stage that data is valid
        * ready_i: input from next stage indicating that it can accept data
        * data_o : an output - MUST be added by the USER of this class
    """
    def __init__(self, stage_ctl=False):
        self.stage_ctl = stage_ctl
        self.valid_o = Signal(name="n_valid_o") # self out>>  next
        self.ready_i = Signal(name="n_ready_i") # self <<in   next
        self.data_o = None # XXX MUST BE ADDED BY USER
        #if self.stage_ctl:
        self.d_valid = Signal(reset=1) # INTERNAL (data valid)
        self.trigger = Signal(reset_less=True)

    @property
    def ready_i_test(self):
        if self.stage_ctl:
            return self.ready_i & self.d_valid
        return self.ready_i

    def connect_to_next(self, nxt):
        """ helper function to connect to the next stage data/valid/ready.
            data/valid is passed *TO* nxt, and ready comes *IN* from nxt.
            use this when connecting stage-to-stage
        """
        return [nxt.valid_i.eq(self.valid_o),
                self.ready_i.eq(nxt.ready_o),
                nmoperator.eq(nxt.data_i, self.data_o),
               ]

    def _connect_out(self, nxt, direct=False, fn=None):
        """ internal helper function to connect stage to an output source.
            do not use to connect stage-to-stage!
        """
        ready_i = nxt.ready_i if direct else nxt.ready_i_test
        data_o = fn(nxt.data_o) if fn is not None else nxt.data_o
        return [nxt.valid_o.eq(self.valid_o),
                self.ready_i.eq(ready_i),
                nmoperator.eq(data_o, self.data_o),
               ]

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.trigger.eq(self.ready_i_test & self.valid_o)
        return m

    def __iter__(self):
        yield self.ready_i
        yield self.valid_o
        if hasattr(self.data_o, "ports"):
            yield from self.data_o.ports()
        elif isinstance(self.data_o, Sequence):
            yield from self.data_o
        else:
            yield self.data_o

    def ports(self):
        return list(self)


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


class StageChain(StageCls):
    """ pass in a list of stages, and they will automatically be
        chained together via their input and output specs into a
        combinatorial chain, to create one giant combinatorial block.

        the end result basically conforms to the exact same Stage API.

        * input to this class will be the input of the first stage
        * output of first stage goes into input of second
        * output of second goes into input into third
        * ... (etc. etc.)
        * the output of this class will be the output of the last stage

        NOTE: whilst this is very similar to ControlBase.connect(), it is
        *really* important to appreciate that StageChain is pure
        combinatorial and bypasses (does not involve, at all, ready/valid
        signalling of any kind).

        ControlBase.connect on the other hand respects, connects, and uses
        ready/valid signalling.

        Arguments:

        * :chain: a chain of combinatorial blocks conforming to the Stage API
                  NOTE: StageChain.ispec and ospect have to have something
                  to return (beginning and end specs of the chain),
                  therefore the chain argument must be non-zero length

        * :specallocate: if set, new input and output data will be allocated
                         and connected (eq'd) to each chained Stage.
                         in some cases if this is not done, the nmigen warning
                         "driving from two sources, module is being flattened"
                         will be issued.

        NOTE: do NOT use StageChain with combinatorial blocks that have
        side-effects (state-based / clock-based input) or conditional
        (inter-chain) dependencies, unless you really know what you are doing.
    """
    def __init__(self, chain, specallocate=False):
        assert len(chain) > 0, "stage chain must be non-zero length"
        self.chain = chain
        self.specallocate = specallocate

    def ispec(self):
        """ returns the ispec of the first of the chain
        """
        return _spec(self.chain[0].ispec, "chainin")

    def ospec(self):
        """ returns the ospec of the last of the chain
        """
        return _spec(self.chain[-1].ospec, "chainout")

    def _specallocate_setup(self, m, i):
        o = i # in case chain is empty
        for (idx, c) in enumerate(self.chain):
            if hasattr(c, "setup"):
                c.setup(m, i)               # stage may have some module stuff
            ofn = self.chain[idx].ospec     # last assignment survives
            o = _spec(ofn, 'chainin%d' % idx)
            m.d.comb += nmoperator.eq(o, c.process(i)) # process input into "o"
            if idx == len(self.chain)-1:
                break
            ifn = self.chain[idx+1].ispec   # new input on next loop
            i = _spec(ifn, 'chainin%d' % (idx+1))
            m.d.comb += nmoperator.eq(i, o) # assign to next input
        return o                            # last loop is the output

    def _noallocate_setup(self, m, i):
        o = i # in case chain is empty
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


class StageHandler: # (Elaboratable):
    """ Stage handling (wrapper) class: makes e.g. static classes "real"
        (instances) and provides a way to allocate data_i and data_o
    """
    def __init__(self, stage): self.stage = stage
    def ispec(self, name): return _spec(self.stage.ispec, name)
    def ospec(self, name): return _spec(self.stage.ospec, name)
    def process(self, i): return self.stage.process(i)

    def setup(self, m, i):
        if self.stage is None or not hasattr(self.stage, "setup"):
            return
        self.stage.setup(m, i)

    def _postprocess(self, i): # XXX DISABLED
        return i # RETURNS INPUT
        if hasattr(self.stage, "postprocess"):
            return self.stage.postprocess(i)
        return i

    def new_data(self, p, n, name):
        """ allocates new data_i and data_o
        """
        return (_spec(p.stage.ispec, "%s_i" % name),
                _spec(n.stage.ospec, "%s_o" % name))


class ControlBase(StageHandler, Elaboratable):
    """ Common functions for Pipeline API.  Note: a "pipeline stage" only
        exists (conceptually) when a ControlBase derivative is handed
        a Stage (combinatorial block)
    """
    def __init__(self, stage=None, in_multi=None, stage_ctl=False):
        """ Base class containing ready/valid/data to previous and next stages

            * p: contains ready/valid to the previous stage
            * n: contains ready/valid to the next stage

            Except when calling Controlbase.connect(), user must also:
            * add data_i member to PrevControl (p) and
            * add data_o member to NextControl (n)
        """
        # set up input and output IO ACK (prev/next ready/valid)
        self.p = PrevControl(in_multi, stage_ctl)
        self.n = NextControl(stage_ctl)

        self.sh = StageHandler(stage)
        if stage is not None:
            self.new_data(self, self, "data")

    def new_data(self, p, n, name):
        """ allocates new data_i and data_o
        """
        self.p.data_i, self.n.data_o = self.sh.new_data(p.sh, n.sh, name)

    @property
    def data_r(self):
        return self.sh.process(self.p.data_i)

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
        eqs = [] # collated list of assignment statements

        # connect inter-chain
        for i in range(len(pipechain)-1):
            pipe1 = pipechain[i]
            pipe2 = pipechain[i+1]
            eqs += pipe1.connect_to_next(pipe2)

        # connect front and back of chain to ourselves
        front = pipechain[0]
        end = pipechain[-1]
        self.new_data(front, end, "chain") # NOTE: REPLACES existing data
        eqs += front._connect_in(self)
        eqs += end._connect_out(self)

        return eqs

    def elaborate(self, platform):
        """ handles case where stage has dynamic ready/valid functions
        """
        m = Module()
        m.submodules.p = self.p
        m.submodules.n = self.n

        self.sh.setup(m, self.p.data_i)

        if not self.p.stage_ctl:
            return m

        stage = self.sh.stage

        # intercept the previous (outgoing) "ready", combine with stage ready
        m.d.comb += self.p.s_ready_o.eq(self.p._ready_o & stage.d_ready)

        # intercept the next (incoming) "ready" and combine it with data valid
        sdv = stage.d_valid(self.n.ready_i)
        m.d.comb += self.n.d_valid.eq(self.n.ready_i & sdv)

        return m

    def set_input(self, i):
        """ helper function to set the input data
        """
        return nmoperator.eq(self.p.data_i, i)

    def __iter__(self):
        yield from self.p
        yield from self.n

    def ports(self):
        return list(self)

