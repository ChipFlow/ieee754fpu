from nmigen import Module, Signal
from nmutil.pipemodbase import PipeModBase
from ieee754.cordic.pipe_data import CordicData, CordicInitialData
import math
import bigfloat as bf
from bigfloat import BigFloat


class CordicInitialStage(PipeModBase):
    def __init__(self, pspec):
        super().__init__(pspec, "cordicinit")

    def ispec(self):
        return CordicInitialData(self.pspec)

    def ospec(self):
        return CordicData(self.pspec)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        An = 1.0
        for i in range(self.pspec.iterations):
            An *= math.sqrt(1 + 2**(-2*i))
        X0 = int(round(self.pspec.M*1/An))

        comb += self.o.x.eq(X0)
        comb += self.o.y.eq(0)
        comb += self.o.z.eq(self.i.z0)

        comb += self.o.ctx.eq(self.i.ctx)
        return m


class CordicStage(PipeModBase):
    def __init__(self, pspec, stagenum):
        super().__init__(pspec, "cordicstage%d" % stagenum)
        self.stagenum = stagenum

    def ispec(self):
        return CordicData(self.pspec)

    def ospec(self):
        return CordicData(self.pspec)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        dx = Signal(self.i.x.shape())
        dy = Signal(self.i.y.shape())
        dz = Signal(self.i.z.shape())
        with bf.quadruple_precision:
            x = bf.atan(BigFloat(2) ** BigFloat(-self.stagenum))
            x = x/(bf.const_pi()/2)
            x = x * self.pspec.M
            angle = int(round(x))

        comb += dx.eq(self.i.y >> self.stagenum)
        comb += dy.eq(self.i.x >> self.stagenum)
        comb += dz.eq(angle)

        with m.If(self.i.z >= 0):
            comb += self.o.x.eq(self.i.x - dx)
            comb += self.o.y.eq(self.i.y + dy)
            comb += self.o.z.eq(self.i.z - dz)
        with m.Else():
            comb += self.o.x.eq(self.i.x + dx)
            comb += self.o.y.eq(self.i.y - dy)
            comb += self.o.z.eq(self.i.z + dz)


        comb += self.o.ctx.eq(self.i.ctx)
        return m
