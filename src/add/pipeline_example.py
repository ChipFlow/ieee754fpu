""" Example 5: Making use of PyRTL and Introspection. """

from nmigen import Module, Signal
from nmigen.cli import main, verilog, rtlil


from pipeline import SimplePipeline, ObjectProxy, PipeManager


class SimplePipelineExample(SimplePipeline):
    """ A very simple pipeline to show how registers are inferred. """

    def __init__(self, pipe):
        SimplePipeline.__init__(self, pipe)
        self._loopback = Signal(4)
        self._setup()

    def stage0(self):
        self.n = ~self._loopback

    def stage1(self):
        self.n = self.n + 2

    def stage2(self):
        localv = Signal(4)
        self._pipe.comb += localv.eq(2)
        self.n = self.n << localv

    def stage3(self):
        self.n = ~self.n

    def stage4(self):
        self._pipe.sync += self._loopback.eq(self.n + 3)


class ObjectBasedPipelineExample(SimplePipeline):
    """ A very simple pipeline to show how registers are inferred. """

    def __init__(self, pipe):
        SimplePipeline.__init__(self, pipe)
        self._loopback = Signal(4)
        o = ObjectProxy(pipe)
        o.a = Signal(4)
        o.b = Signal(4)
        self._obj = o
        self._setup()

    def stage0(self):
        self.n = ~self._loopback
        self.o = self._obj

    def stage1(self):
        self.n = self.n + self.o.a
        o = ObjectProxy(self._pipe)
        o.a = self.n
        o.b = self.o.b
        self.o = o

    def stage2(self):
        localv = Signal(4)
        self._pipe.comb += localv.eq(2)
        self.n = self.n << localv
        o = ObjectProxy(self._pipe)
        o.b = self.n + self.o.a + self.o.b
        self.o = o

    def stage3(self):
        self.n = ~self.n
        self.o = self.o
        self.o.b = self.o.b + self.n

    def stage4(self):
        self._pipe.sync += self._loopback.eq(self.n + 3 + self.o.b)


class PipeModule:

    def __init__(self):
        self.m = Module()
        self.p = ObjectBasedPipelineExample(self.m.d)

    def get_fragment(self, platform=None):
        return self.m


class PipelineStageExample(PipeManager):

    def __init__(self):
        self.m = Module()
        self._loopback = Signal(4)
        PipeManager.__init__(self, self.m)

    def stage0(self):
        self.n = ~self._loopback

    def stage1(self):
        self.n = self.n + 2

    def stage2(self):
        localv = Signal(4)
        self._pipe.comb += localv.eq(2)
        self.n = self.n << localv

    def stage3(self):
        self.n = ~self.n

    def stage4(self):
        self._pipe.sync += self._loopback.eq(self.n + 3)

    def get_fragment(self, platform=None):

        with self.Stage() as (p, m):
            p.n = ~self._loopback
        with self.Stage(p) as (p, m):
            p.n = p.n + 2
        with self.Stage(p) as (p, m):
            localv = Signal(4)
            m.d.comb += localv.eq(2)
            p.n = p.n << localv

        return self.m



if __name__ == "__main__":
    example = PipeModule()
    with open("pipe_module.il", "w") as f:
        f.write(rtlil.convert(example, ports=[
               example.p._loopback,
             ]))
    example = PipelineStageExample()
    with open("pipe_stage_module.il", "w") as f:
        f.write(rtlil.convert(example, ports=[
               example._loopback,
             ]))
