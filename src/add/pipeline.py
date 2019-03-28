""" Example 5: Making use of PyRTL and Introspection. """

from nmigen import Signal
from nmigen.compat.fhdl.bitcontainer import value_bits_sign

# The following example shows how pyrtl can be used to make some interesting
# hardware structures using python introspection.  In particular, this example
# makes a N-stage pipeline structure.  Any specific pipeline is then a derived
# class of SimplePipeline where methods with names starting with "stage" are
# stages, and new members with names not starting with "_" are to be registered
# for the next stage.

from singlepipe import eq

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
        new_pipereg = Signal(value_bits_sign(value), name=rname,
                             reset_less=True)
        if next_stage not in self._pipeline_register_map:
            self._pipeline_register_map[next_stage] = {}
        self._pipeline_register_map[next_stage][name] = new_pipereg
        self._pipe.sync += eq(new_pipereg, value)

