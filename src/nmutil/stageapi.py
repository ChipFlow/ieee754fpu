""" Stage API

    Associated development bugs:
    * http://bugs.libre-riscv.org/show_bug.cgi?id=64
    * http://bugs.libre-riscv.org/show_bug.cgi?id=57

    Stage API:
    ---------

    stage requires compliance with a strict API that may be
    implemented in several means, including as a static class.

    Stages do not HOLD data, and they definitely do not contain
    signalling (ready/valid).  They do however specify the FORMAT
    of the incoming and outgoing data, and they provide a means to
    PROCESS that data (from incoming format to outgoing format).

    Stage Blocks really should be combinatorial blocks (Moore FSMs).
    It would be ok to have input come in from sync'd sources
    (clock-driven, Mealy FSMs) however by doing so they would no longer
    be deterministic, and chaining such blocks with such side-effects
    together could result in unexpected, unpredictable, unreproduceable
    behaviour.

    So generally to be avoided, then unless you know what you are doing.
    https://en.wikipedia.org/wiki/Moore_machine
    https://en.wikipedia.org/wiki/Mealy_machine

    the methods of a stage instance must be as follows:

    * ispec() - Input data format specification.  Takes a bit of explaining.
                The requirements are: something that eventually derives from
                nmigen Value must be returned *OR* an iterator or iterable
                or sequence (list, tuple etc.) or generator must *yield*
                thing(s) that (eventually) derive from the nmigen Value class.

                Complex to state, very simple in practice:
                see test_buf_pipe.py for over 25 worked examples.

    * ospec() - Output data format specification.
                format requirements identical to ispec.

    * process(m, i) - Optional function for processing ispec-formatted data.
                returns a combinatorial block of a result that
                may be assigned to the output, by way of the "nmoperator.eq"
                function.  Note that what is returned here can be
                extremely flexible.  Even a dictionary can be returned
                as long as it has fields that match precisely with the
                Record into which its values is intended to be assigned.
                Again: see example unit tests for details.

    * setup(m, i) - Optional function for setting up submodules.
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

    StageHelper:
    ----------

    A convenience wrapper around a Stage-API-compliant "thing" which
    complies with the Stage API and provides mandatory versions of
    all the optional bits.
"""

from abc import ABCMeta, abstractmethod
import inspect

from nmutil import nmoperator


def _spec(fn, name=None):
    """ useful function that determines if "fn" has an argument "name".
        if so, fn(name) is called otherwise fn() is called.

        means that ispec and ospec can be declared with *or without*
        a name argument.  normally it would be necessary to have
        "ispec(name=None)" to achieve the same effect.
    """
    if name is None:
        return fn()
    varnames = dict(inspect.getmembers(fn.__code__))['co_varnames']
    if 'name' in varnames:
        return fn(name=name)
    return fn()


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
    #@abstractmethod
    #def process(self, i): pass  # OPTIONAL


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

    #@staticmethod
    #@abstractmethod
    #def process(i): pass


class StageHelper(Stage):
    """ a convenience wrapper around something that is Stage-API-compliant.
        (that "something" may be a static class, for example).

        StageHelper happens to also be compliant with the Stage API,
        it differs from the stage that it wraps in that all the "optional"
        functions are provided (hence the designation "convenience wrapper")
    """
    def __init__(self, stage):
        self.stage = stage
        self._ispecfn = None
        self._ospecfn = None
        if stage is not None:
            self.set_specs(self, self)

    def ospec(self, name):
        assert self._ospecfn is not None
        return _spec(self._ospecfn, name)

    def ispec(self, name):
        assert self._ispecfn is not None
        return _spec(self._ispecfn, name)

    def set_specs(self, p, n):
        """ sets up the ispecfn and ospecfn for getting input and output data
        """
        if hasattr(p, "stage"):
            p = p.stage
        if hasattr(n, "stage"):
            n = n.stage
        self._ispecfn = p.ispec
        self._ospecfn = n.ospec

    def new_specs(self, name):
        """ allocates new ispec and ospec pair
        """
        return (_spec(self.ispec, "%s_i" % name),
                _spec(self.ospec, "%s_o" % name))

    def process(self, i):
        if self.stage and hasattr(self.stage, "process"):
            return self.stage.process(i)
        return i

    def setup(self, m, i):
        if self.stage is not None and hasattr(self.stage, "setup"):
            self.stage.setup(m, i)

    def _postprocess(self, i): # XXX DISABLED
        return i # RETURNS INPUT
        if hasattr(self.stage, "postprocess"):
            return self.stage.postprocess(i)
        return i


class StageChain(StageHelper):
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
        StageHelper.__init__(self, None)
        self.setup = self._sa_setup if specallocate else self._na_setup
        self.set_specs(self.chain[0], self.chain[-1])

    def _sa_setup(self, m, i):
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
        self.o = o
        return self.o                       # last loop is the output

    def _na_setup(self, m, i):
        for (idx, c) in enumerate(self.chain):
            if hasattr(c, "setup"):
                c.setup(m, i)               # stage may have some module stuff
            i = o = c.process(i)            # store input into "o"
        self.o = o
        return self.o                       # last loop is the output

    def process(self, i):
        return self.o # conform to Stage API: return last-loop output


