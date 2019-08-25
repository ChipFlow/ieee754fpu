"""IEEE754 Floating Point Library

Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

"""

from nmigen import Module, Signal, Mux
from nmigen.cli import main, verilog

from nmutil.pipemodbase import PipeModBase
from ieee754.fpcommon.fpbase import FPNumBaseRecord
from ieee754.fpcommon.fpbase import MultiShiftRMerge
from ieee754.fpcommon.denorm import FPSCData
from ieee754.fpcommon.getop import FPPipeContext
from ieee754.fpcommon.pscdata import FPSCData


class FPAddAlignMultiMod:
    """Module to do mantissa alignment shift in multiple cycles
    """
    def __init__(self, width):
        self.in_a = FPNumBaseRecord(width)
        self.in_b = FPNumBaseRecord(width)
        self.out_a = FPNumBaseRecord(width)
        self.out_b = FPNumBaseRecord(width)
        self.exp_eq = Signal(reset_less=True)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        # exponent of a greater than b: shift b down
        comb += self.exp_eq.eq(0)
        comb += self.out_a.eq(self.in_a)
        comb += self.out_b.eq(self.in_b)
        agtb = Signal(reset_less=True)
        altb = Signal(reset_less=True)
        comb += agtb.eq(self.in_a.e > self.in_b.e)
        comb += altb.eq(self.in_a.e < self.in_b.e)
        with m.If(agtb):
            comb += self.out_b.shift_down(self.in_b)
        # exponent of b greater than a: shift a down
        with m.Elif(altb):
            comb += self.out_a.shift_down(self.in_a)
        # exponents equal: move to next stage.
        with m.Else():
            comb += self.exp_eq.eq(1)
        return m


class FPAddAlignSingleMod(PipeModBase):

    def __init__(self, pspec):
        super().__init__(pspec, "align")

    def ispec(self):
        return FPSCData(self.pspec, True)

    def ospec(self):
        return FPSCData(self.pspec, True)

    def elaborate(self, platform):
        """ Aligns A against B or B against A, depending on which has the
            greater exponent.  This is done in a *single* cycle using
            variable-width bit-shift

            the shifter used here is quite expensive in terms of gates.
            Mux A or B in (and out) into temporaries, as only one of them
            needs to be aligned against the other.

            code is therefore slightly complex because after testing which
            exponent is greater, a and b get mux-routed into the multi-shifter
            and so does the output.
        """
        m = Module()
        comb = m.d.comb

        ai = self.i.a
        bi = self.i.b
        width = self.pspec.width
        espec = (len(ai.e), True)

        # temporary (muxed) input and output to be shifted
        t_inp = FPNumBaseRecord(width)
        t_out = FPNumBaseRecord(width)
        msr = MultiShiftRMerge(ai.m_width, espec)
        m.submodules.multishift_r = msr

        # temporaries
        ediff = Signal(espec, reset_less=True)
        ediffr = Signal(espec, reset_less=True)
        tdiff = Signal(espec, reset_less=True)
        elz = Signal(reset_less=True)
        egz = Signal(reset_less=True)

        # connect multi-shifter to t_inp/out mantissa (and tdiff)
        # (only one: input/output is muxed)
        comb += msr.inp.eq(t_inp.m)
        comb += msr.diff.eq(tdiff)
        comb += t_out.m.eq(msr.m)
        comb += t_out.e.eq(Mux(egz, ai.e, bi.e))
        comb += t_out.s.eq(t_inp.s)

        # work out exponent difference, set up mux-tests if a > b or b > a
        comb += ediff.eq(ai.e - bi.e)   # a - b
        comb += ediffr.eq(-ediff)                   # b - a
        comb += elz.eq(ediffr > 0)     # ae < be
        comb += egz.eq(ediff > 0)    # ae > be

        # decide what to input into the multi-shifter
        comb += [t_inp.s.eq(Mux(egz, bi.s, ai.s)), # a/b sign
                 t_inp.m.eq(Mux(egz, bi.m, ai.m)), # a/b mantissa
                 t_inp.e.eq(Mux(egz, bi.e, ai.e)), # a/b exponent
                 tdiff.eq(Mux(egz, ediff, ediffr)),
                ]

        # now decide where (if) to route the *output* of the multi-shifter

        # if a exponent greater, route mshifted-out to b? otherwise just b
        comb += [self.o.b.e.eq(Mux(egz, t_out.e, bi.e)), # exponent
                 self.o.b.m.eq(Mux(egz, t_out.m, bi.m)), # mantissa
                 self.o.b.s.eq(bi.s),                    # sign as-is
        ]
        # if b exponent greater, route mshifted-out to a? otherwise just a
        comb += [self.o.a.e.eq(Mux(elz, t_out.e, ai.e)), # exponent
                 self.o.a.m.eq(Mux(elz, t_out.m, ai.m)), # mantissa
                 self.o.a.s.eq(ai.s),                    # sign as-is
        ]

        # pass context through
        comb += self.o.ctx.eq(self.i.ctx)
        comb += self.o.z.eq(self.i.z)
        comb += self.o.out_do_z.eq(self.i.out_do_z)
        comb += self.o.oz.eq(self.i.oz)

        return m

