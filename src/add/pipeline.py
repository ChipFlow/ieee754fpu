""" Example 5: Making use of PyRTL and Introspection. """

from nmigen import Signal
from nmigen.hdl.rec import Record
from nmigen import tracer
from nmigen.compat.fhdl.bitcontainer import value_bits_sign

from singlepipe import eq


# The following example shows how pyrtl can be used to make some interesting
# hardware structures using python introspection.  In particular, this example
# makes a N-stage pipeline structure.  Any specific pipeline is then a derived
# class of SimplePipeline where methods with names starting with "stage" are
# stages, and new members with names not starting with "_" are to be registered
# for the next stage.


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
        if isinstance(value, ObjectProxy):
            new_pipereg = ObjectProxy.like(self._pipe, value,
                                           name=rname, reset_less=True)
        else:
            new_pipereg = Signal.like(value, name=rname, reset_less=True)

        object.__setattr__(self, name, new_pipereg)
        self._pipe.sync += eq(new_pipereg, value)


class SimplePipeline(object):
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

