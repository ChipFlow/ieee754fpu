""" Example 5: Making use of PyRTL and Introspection. """

from collections.abc import Sequence

from nmigen import Signal
from nmigen.hdl.rec import Record
from nmigen import tracer
from nmigen.compat.fhdl.bitcontainer import value_bits_sign
from contextlib import contextmanager

from singlepipe import eq, StageCls, ControlBase, BufferedPipeline
from singlepipe import UnbufferedPipeline


# The following example shows how pyrtl can be used to make some interesting
# hardware structures using python introspection.  In particular, this example
# makes a N-stage pipeline structure.  Any specific pipeline is then a derived
# class of SimplePipeline where methods with names starting with "stage" are
# stages, and new members with names not starting with "_" are to be registered
# for the next stage.

def like(value, rname, pipe):
    if isinstance(value, ObjectProxy):
        return ObjectProxy.like(pipe, value, name=rname, reset_less=True)
    else:
        return Signal(value_bits_sign(value), name=rname,
                             reset_less=True)
        return Signal.like(value, name=rname, reset_less=True)


class ObjectProxy:
    def __init__(self, pipe, name=None):
        self._pipe = pipe
        if name is None:
            name = tracer.get_var_name(default=None)
        self.name = name

    @classmethod
    def like(cls, pipe, value, name=None, src_loc_at=0, **kwargs):
        name = name or tracer.get_var_name(depth=2 + src_loc_at,
                                            default="$like")

        src_loc_at_1 = 1 + src_loc_at
        r = ObjectProxy(pipe, value.name)
        for a in value.ports():
            aname = a.name
            setattr(r, aname, a)
        return r

    def eq(self, i):
        res = []
        for a in self.ports():
            aname = a.name
            ai = getattr(i, aname)
            res.append(a.eq(ai))
        return res

    def ports(self):
        res = []
        for aname in dir(self):
            a = getattr(self, aname)
            if isinstance(a, Signal) or isinstance(a, ObjectProxy) or \
               isinstance(a, Record):
                res.append(a)
        return res

    def __setattr__(self, name, value):
        if name.startswith('_') or name == 'name':
            # do not do anything tricky with variables starting with '_'
            object.__setattr__(self, name, value)
            return
        #rname = "%s_%s" % (self.name, name)
        rname = name
        new_pipereg = like(value, rname, self._pipe)
        object.__setattr__(self, name, new_pipereg)
        self._pipe.sync += eq(new_pipereg, value)


class PipelineStage:
    """ Pipeline builder stage with auto generation of pipeline registers.
    """

    def __init__(self, name, m, prev=None, pipemode=False):
        self._m = m
        self._stagename = name
        self._preg_map = {}
        self._prev_stage = prev
        if prev:
            print ("prev", prev._stagename, prev._preg_map)
            if prev._stagename in prev._preg_map:
                m = prev._preg_map[prev._stagename]
                self._preg_map[prev._stagename] = m
                for k, v in m.items():
                    m[k] = like(v, k, self._m)
            if '__nextstage__' in prev._preg_map:
                m = prev._preg_map['__nextstage__']
                self._preg_map[self._stagename] = m
                for k, v in m.items():
                    m[k] = like(v, k, self._m)
                print ("make current", self._stagename, m)
        self._pipemode = pipemode
        self._eqs = []

    def __getattr__(self, name):
        try:
            v = self._preg_map[self._stagename][name]
            return v
            #return like(v, name, self._m)
        except KeyError:
            raise AttributeError(
                'error, no pipeline register "%s" defined for stage %s'
                % (name, self._stagename))

    def __setattr__(self, name, value):
        if name.startswith('_'):
            # do not do anything tricky with variables starting with '_'
            object.__setattr__(self, name, value)
            return
        pipereg_id = self._stagename
        rname = 'pipereg_' + pipereg_id + '_' + name
        new_pipereg = like(value, rname, self._m)
        next_stage = '__nextstage__'
        if next_stage not in self._preg_map:
            self._preg_map[next_stage] = {}
        self._preg_map[next_stage][name] = new_pipereg
        if self._pipemode:
            self._eqs.append(value)
            print ("!pipemode: append", new_pipereg, value)
            #self._m.d.comb += assign
        else:
            print ("!pipemode: assign", new_pipereg, value)
            assign = eq(new_pipereg, value)
            self._m.d.sync += assign


class AutoStage(StageCls):
    def __init__(self, inspecs, outspecs, eqs):
        self.inspecs, self.outspecs, self.eqs = inspecs, outspecs, eqs
    def ispec(self): return self.inspecs
    def ospec(self): return self.outspecs
    def process(self, i):
        return self.eqs
    #def setup(self, m, i): #m.d.comb += self.eqs


class PipeManager:
    def __init__(self, m, pipemode=False):
        self.m = m
        self.pipemode = pipemode

    @contextmanager
    def Stage(self, name, prev=None):
        stage = PipelineStage(name, self.m, prev, self.pipemode)
        try:
            yield stage, stage._m
        finally:
            pass
        if self.pipemode:
            inspecs = self.get_specs(stage, name)
            outspecs = self.get_specs(stage, '__nextstage__', liked=True)
            s = AutoStage(inspecs, outspecs, stage._eqs)
            self.stages.append(s)

    def get_specs(self, stage, name, liked=False):
        if name in stage._preg_map:
            res = []
            for k, v in stage._preg_map[name].items():
                #v = like(v, k, stage._m)
                res.append(v)
            return res
        return []

    def __enter__(self):
        self.stages = []
        return self

    def __exit__(self, *args):
        print (args)
        pipes = []
        cb = ControlBase()
        for s in self.stages:
            print (s, s.inspecs, s.outspecs)
            p = UnbufferedPipeline(s)
            pipes.append(p)
            self.m.submodules += p

        #self.m.d.comb += cb.connect(pipes)


class SimplePipeline:
    """ Pipeline builder with auto generation of pipeline registers.
    """

    def __init__(self, pipe):
        self._pipe = pipe
        self._pipeline_register_map = {}
        self._current_stage_num = 0

    def _setup(self):
        stage_list = []
        for method in dir(self):
            if method.startswith('stage'):
                stage_list.append(method)
        for stage in sorted(stage_list):
            stage_method = getattr(self, stage)
            stage_method()
            self._current_stage_num += 1

    def __getattr__(self, name):
        try:
            return self._pipeline_register_map[self._current_stage_num][name]
        except KeyError:
            raise AttributeError(
                'error, no pipeline register "%s" defined for stage %d'
                % (name, self._current_stage_num))

    def __setattr__(self, name, value):
        if name.startswith('_'):
            # do not do anything tricky with variables starting with '_'
            object.__setattr__(self, name, value)
            return
        next_stage = self._current_stage_num + 1
        pipereg_id = str(self._current_stage_num) + 'to' + str(next_stage)
        rname = 'pipereg_' + pipereg_id + '_' + name
        #new_pipereg = Signal(value_bits_sign(value), name=rname,
        #                     reset_less=True)
        if isinstance(value, ObjectProxy):
            new_pipereg = ObjectProxy.like(self._pipe, value,
                                           name=rname, reset_less = True)
        else:
            new_pipereg = Signal.like(value, name=rname, reset_less = True)
        if next_stage not in self._pipeline_register_map:
            self._pipeline_register_map[next_stage] = {}
        self._pipeline_register_map[next_stage][name] = new_pipereg
        self._pipe.sync += eq(new_pipereg, value)

