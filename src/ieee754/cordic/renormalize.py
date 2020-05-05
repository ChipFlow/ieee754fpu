from nmigen import Module, Signal, Mux, Elaboratable, unsigned
from nmutil.pipemodbase import PipeModBase
from nmutil.clz import CLZ
from ieee754.cordic.pipe_data import CordicData, CordicOutputData
from ieee754.fpcommon.fpbase import FPNumBaseRecord


class Norm(Elaboratable):
    def __init__(self, pspec):
        self.sig_in = Signal(range(-pspec.M, pspec.M+1))

        self.sig_out = Signal(pspec.width)
        self.width = pspec.width

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        numrec = FPNumBaseRecord(self.width, False)

        sign = Signal(1)
        comb += sign.eq(self.sig_in[-1])

        absv = Signal.like(self.sig_in)
        comb += absv.eq(Mux(sign, -self.sig_in, self.sig_in))

        m.submodules.clzx = clz = CLZ(self.sig_in.width)

        count = Signal.like(clz.lz)

        comb += clz.sig_in.eq(absv)
        comb += count.eq(clz.lz)

        normalized = Signal(unsigned(self.sig_in.width))

        comb += normalized.eq(absv << (count-1))

        comb += numrec.m.eq(normalized[-(numrec.m_width+1):-1])
        comb += numrec.s.eq(sign)
        comb += numrec.e.eq(-count+1)
        
        comb += self.sig_out.eq(numrec.create2(numrec.s, numrec.e, numrec.m))
        return m

class CordicRenormalize(PipeModBase):
    def __init__(self, pspec):
        super().__init__(pspec, "cordicrenorm")

    def ispec(self):
        return CordicData(self.pspec)

    def ospec(self):
        return CordicOutputData(self.pspec)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        m.submodules.normx = normx = Norm(self.pspec)
        m.submodules.normy = normy = Norm(self.pspec)

        comb += [
            normx.sig_in.eq(self.i.x),
            normy.sig_in.eq(self.i.y),
        ]

        comb += self.o.x.eq(normx.sig_out)
        comb += self.o.y.eq(normy.sig_out)

        return m
