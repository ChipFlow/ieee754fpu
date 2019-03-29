""" Example 5: Making use of PyRTL and Introspection. """

from nmigen import Module, Signal
from nmigen.cli import main, verilog


from pipeline import SimplePipeline, ObjectProxy


class SimplePipelineExample(SimplePipeline):
    """ A very simple pipeline to show how registers are inferred. """

    def __init__(self, pipe):
        SimplePipeline.__init__(self, pipe)
        self._loopback = Signal(4)
        self._obj = ObjectProxy(pipe)
        self._obj.a = Signal(4)
        self._obj.b = Signal(4)
        self._setup()

    def stage0(self):
        self.n = ~self._loopback
        self.o = self._obj

    def stage1(self):
        self.n = self.n + self.o.a
        self.o = self.o
        self.o.a = self.n
        self.o.b = self.o.b

    def stage2(self):
        localv = Signal(4)
        self._pipe.comb += localv.eq(2)
        self.n = self.n << localv
        self.o = self.o
        self.o.b = self.n + self.o.a + self.o.b

    def stage3(self):
        self.n = ~self.n
        self.o = self.o
        self.o.b = self.o.b + self.n

    def stage4(self):
        self.o.b = self.o.b
        self._pipe.sync += self._loopback.eq(self.n + 3 + self.o.b)

class PipeModule:

    def __init__(self):
        self.m = Module()
        self.p = SimplePipelineExample(self.m.d)

    def get_fragment(self, platform=None):
        return self.m

if __name__ == "__main__":
    example = PipeModule()
    main(example, ports=[
                    example.p._loopback,
        ])

    #print(verilog.convert(example, ports=[
    #           example.p._loopback,
    #         ]))
