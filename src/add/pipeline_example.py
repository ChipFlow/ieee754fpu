""" Example 5: Making use of PyRTL and Introspection. """

from nmigen import Module, Signal, Const
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

    def __init__(self, m):
        SimplePipeline.__init__(self, m)
        self._loopback = Signal(4)
        o = ObjectProxy(m)
        o.a = Signal(4)
        o.b = Signal(4)
        self._obj = o
        self._setup()

    def stage0(self):
        self.n = ~self._loopback
        self.o = self._obj

    def stage1(self):
        self.n = self.n + self.o.a
        o = ObjectProxy(self._m)
        o.c = self.n
        o.d = self.o.b + self.n + Const(5)
        self.o = o

    def stage2(self):
        localv = Signal(4)
        self._m.d.comb += localv.eq(2)
        self.n = self.n << localv
        o = ObjectProxy(self._m)
        o.e = self.n + self.o.c + self.o.d
        self.o = o

    def stage3(self):
        self.n = ~self.n
        self.o = self.o
        self.o.e = self.o.e + self.n

    def stage4(self):
        self._m.d.sync += self._loopback.eq(self.n + 3 + self.o.e)


class PipeModule:

    def __init__(self):
        self.m = Module()
        self.p = ObjectBasedPipelineExample(self.m)

    def elaborate(self, platform=None):
        return self.m


class PipelineStageExample:

    def __init__(self):
        self._loopback = Signal(4, name="loopback")

    def elaborate(self, platform=None):

        m = Module()

        with PipeManager(m, pipemode=True) as pipe:

            ispec={'loopback': self._loopback}
            with pipe.Stage("first", ispec=ispec) as (p, m):
                p.n = ~p.loopback
            with pipe.Stage("second", p) as (p, m):
                #p.n = ~self._loopback + 2
                p.n = p.n + Const(2)
            with pipe.Stage("third", p) as (p, m):
                #p.n = ~self._loopback + 5
                localv = Signal(4)
                m.d.comb += localv.eq(2)
                p.n = p.n << localv + Const(1)
                #p.m = p.n + 2

        print (pipe.stages)

        return m

class PipelineStageObjectExample:

    def __init__(self):
        self.loopback = Signal(4)

    def elaborate(self, platform=None):

        m = Module()

        o = ObjectProxy(None, pipemode=False)
        o.a = Signal(4)
        o.b = Signal(4)
        self.obj = o

        localv2 = Signal(4)
        m.d.sync += localv2.eq(localv2 + 3)

        #m.d.comb += self.obj.a.eq(localv2 + 1)
        #m.d.sync += self._loopback.eq(localv2)

        ispec= {'loopback': self.loopback, 'obj': self.obj}
        with PipeManager(m, pipemode=True) as pipe:

            with pipe.Stage("first", ispec=ispec) as (p, m):
                p.n = ~p.loopback
                p.o = p.obj
            with pipe.Stage("second", p) as (p, m):
                #p.n = ~self.loopback + 2
                localn = Signal(4)
                m.d.comb += localn.eq(p.n)
                o = ObjectProxy(None, pipemode=False)
                o.c = localn
                o.d = p.o.b + localn + Const(5)
                p.n = localn
                p.o = o
            with pipe.Stage("third", p) as (p, m):
                #p.n = ~self._loopback + 5
                localv = Signal(4)
                m.d.comb += localv.eq(2)
                p.n = p.n << localv
                o = ObjectProxy(None, pipemode=False)
                o.e = p.n + p.o.c + p.o.d
                p.o = o

        print ("stages", pipe.stages)

        return m


class PipelineStageObjectExample2:

    def __init__(self):
        self._loopback = Signal(4)

    def elaborate(self, platform=None):

        m = Module()

        ispec= [self._loopback]
        with PipeManager(m, pipemode=True) as pipe:

            with pipe.Stage("first",
                            ispec=ispec) as (p, m):
                p.n = ~self._loopback
                o = ObjectProxy(None, pipemode=False)
                o.b = ~self._loopback + Const(5)
                p.o = o

        print ("stages", pipe.stages)

        return m



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
    #exit(0)
    example = PipelineStageObjectExample()
    with open("pipe_stage_object_module.il", "w") as f:
        f.write(rtlil.convert(example, ports=[
               example.loopback,
             ]))
