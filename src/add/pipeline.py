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

def like(value, rname, pipe, pipemode=False):
    if isinstance(value, ObjectProxy):
        return ObjectProxy.like(pipe, value, pipemode=pipemode,
                                name=rname, reset_less=True)
    else:
        return Signal(value_bits_sign(value), name=rname,
                             reset_less=True)
        return Signal.like(value, name=rname, reset_less=True)

def get_eqs(_eqs):
    eqs = []
    for e in _eqs:
        if isinstance(e, ObjectProxy):
            eqs += get_eqs(e._eqs)
        else:
            eqs.append(e)
    return eqs


class ObjectProxy:
    def __init__(self, m, name=None, pipemode=False):
        self._m = m
        if name is None:
            name = tracer.get_var_name(default=None)
        self.name = name
        self._pipemode = pipemode
        self._eqs = []
        self._preg_map = {}

    @classmethod
    def like(cls, m, value, pipemode=False, name=None, src_loc_at=0, **kwargs):
        name = name or tracer.get_var_name(depth=2 + src_loc_at,
                                            default="$like")

        src_loc_at_1 = 1 + src_loc_at
        r = ObjectProxy(m, value.name, pipemode)
        #for a, aname in value._preg_map.items():
        #    r._preg_map[aname] = like(a, aname, m, pipemode)
        for a in value.ports():
            aname = a.name
            r._preg_map[aname] = like(a, aname, m, pipemode)
        return r

    def __repr__(self):
        subobjs = []
        for a in self.ports():
            aname = a.name
            ai = self._preg_map[aname]
            subobjs.append(repr(ai))
        return "<OP %s>" % subobjs

    def eq(self, i):
        print ("ObjectProxy eq", self, i)
        res = []
        for a in self.ports():
            aname = a.name
            ai = i._preg_map[aname]
            res.append(a.eq(ai))
        return res

    def ports(self):
        res = []
        for aname, a in self._preg_map.items():
            if isinstance(a, Signal) or isinstance(a, ObjectProxy) or \
               isinstance(a, Record):
                res.append(a)
        print ("ObjectPorts", res)
        return res

    def __getattr__(self, name):
        try:
            v = self._preg_map[name]
            return v
            #return like(v, name, self._m)
        except KeyError:
            raise AttributeError(
                'error, no pipeline register "%s" defined for OP %s'
                % (name, self.name))

    def __setattr__(self, name, value):
        if name.startswith('_') or name in ['name', 'ports', 'eq', 'like']:
            # do not do anything tricky with variables starting with '_'
            object.__setattr__(self, name, value)
            return
        #rname = "%s_%s" % (self.name, name)
        rname = name
        new_pipereg = like(value, rname, self._m, self._pipemode)
        self._preg_map[name] = new_pipereg
        #object.__setattr__(self, name, new_pipereg)
        if self._pipemode:
            print ("OP pipemode", new_pipereg, value)
            #self._eqs.append(value)
            #self._m.d.comb += eq(new_pipereg, value)
            pass
        elif self._m:
            print ("OP !pipemode assign", new_pipereg, value, type(value))
            self._m.d.comb += eq(new_pipereg, value)


class PipelineStage:
    """ Pipeline builder stage with auto generation of pipeline registers.
    """

    def __init__(self, name, m, prev=None, pipemode=False, ispec=None):
        self._m = m
        self._stagename = name
        self._preg_map = {}
        self._prev_stage = prev
        self._ispec = ispec
        if prev:
            print ("prev", prev._stagename, prev._preg_map)
            if prev._stagename in prev._preg_map:
                m = prev._preg_map[prev._stagename]
                self._preg_map[prev._stagename] = m
                #for k, v in m.items():
                    #m[k] = like(v, k, self._m)
            if '__nextstage__' in prev._preg_map:
                m = prev._preg_map['__nextstage__']
                self._preg_map[self._stagename] = m
                #for k, v in m.items():
                    #m[k] = like(v, k, self._m)
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
        new_pipereg = like(value, rname, self._m, self._pipemode)
        next_stage = '__nextstage__'
        if next_stage not in self._preg_map:
            self._preg_map[next_stage] = {}
        self._preg_map[next_stage][name] = new_pipereg
        if self._pipemode:
            self._eqs.append(value)
            print ("pipemode: append", new_pipereg, value)
            #self._m.d.comb += assign
        else:
            print ("!pipemode: assign", new_pipereg, value)
            assign = eq(new_pipereg, value)
            self._m.d.sync += assign


class AutoStage(StageCls):
    def __init__(self, inspecs, outspecs, eqs):
        self.inspecs, self.outspecs, self.eqs = inspecs, outspecs, eqs
        self.o = self.ospec()
    def ispec(self): return self.like(self.inspecs)
    def ospec(self): return self.like(self.outspecs)
    def like(self, specs):
        res = []
        for v in specs:
            res.append(like(v, v.name, None, pipemode=True))
        return res

    def process(self, i):
        print ("stage process", i)
        return self.o

    def setup(self, m, i):
        print ("stage setup", i)
        m.d.sync += eq(i, self.eqs)
        m.d.comb += eq(self.o, i)


class PipeManager:
    def __init__(self, m, pipemode=False, pipetype=None):
        self.m = m
        self.pipemode = pipemode
        self.pipetype = pipetype

    @contextmanager
    def Stage(self, name, prev=None, ispec=None):
        print ("start stage", name)
        stage = PipelineStage(name, self.m, prev, self.pipemode, ispec=ispec)
        try:
            yield stage, stage._m
        finally:
            pass
        if self.pipemode:
            if stage._ispec:
                print ("use ispec", stage._ispec)
                inspecs = stage._ispec
            else:
                inspecs = self.get_specs(stage, name)
            outspecs = self.get_specs(stage, '__nextstage__', liked=True)
            eqs = get_eqs(stage._eqs)
            print ("stage eqs", name, eqs)
            s = AutoStage(inspecs, outspecs, eqs)
            self.stages.append(s)
        print ("end stage", name, "\n")

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
        print ("exit stage", args)
        pipes = []
        cb = ControlBase()
        for s in self.stages:
            print ("stage specs", s, s.inspecs, s.outspecs)
            if self.pipetype == 'buffered':
                p = BufferedPipeline(s)
            else:
                p = UnbufferedPipeline(s)
            pipes.append(p)
            self.m.submodules += p

        self.m.d.comb += cb.connect(pipes)


class SimplePipeline:
    """ Pipeline builder with auto generation of pipeline registers.
    """

    def __init__(self, m):
        self._m = m
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
            new_pipereg = ObjectProxy.like(self._m, value,
                                           name=rname, reset_less = True)
        else:
            new_pipereg = Signal.like(value, name=rname, reset_less = True)
        if next_stage not in self._pipeline_register_map:
            self._pipeline_register_map[next_stage] = {}
        self._pipeline_register_map[next_stage][name] = new_pipereg
        self._m.d.sync += eq(new_pipereg, value)

