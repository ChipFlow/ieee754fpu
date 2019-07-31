# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal
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
            needs to be aligned against the other
        """
        m = Module()
        comb = m.d.comb

        # temporary (muxed) input and output to be shifted
        width = self.pspec.width
        espec = (len(self.i.a.e), True)

        t_inp = FPNumBaseRecord(width)
        t_out = FPNumBaseRecord(width)
        msr = MultiShiftRMerge(self.i.a.m_width, espec)
        m.submodules.multishift_r = msr

        # temporaries
        ediff = Signal(espec, reset_less=True)
        ediffr = Signal(espec, reset_less=True)
        tdiff = Signal(espec, reset_less=True)
        elz = Signal(reset_less=True)
        egz = Signal(reset_less=True)

        with m.If(~self.i.out_do_z):
            # connect multi-shifter to t_inp/out mantissa (and tdiff)
            # (only one: input/output is muxed)
            comb += msr.inp.eq(t_inp.m)
            comb += msr.diff.eq(tdiff)
            comb += t_out.m.eq(msr.m)
            comb += t_out.e.eq(t_inp.e + tdiff)
            comb += t_out.s.eq(t_inp.s)

            comb += ediff.eq(self.i.a.e - self.i.b.e)   # a - b
            comb += ediffr.eq(-ediff)                   # b - a
            comb += elz.eq(self.i.a.e < self.i.b.e)     # ae < be
            comb += egz.eq(self.i.a.e > self.i.b.e)     # ae > be

            # default: A-exp == B-exp, A and B untouched (fall through)
            comb += self.o.a.eq(self.i.a)
            comb += self.o.b.eq(self.i.b)

            # exponent of a greater than b: shift b down
            with m.If(egz):
                comb += [t_inp.eq(self.i.b),
                             tdiff.eq(ediff),
                             self.o.b.eq(t_out),
                             self.o.b.s.eq(self.i.b.s), # whoops forgot sign
                            ]
            # exponent of b greater than a: shift a down
            with m.Elif(elz):
                comb += [t_inp.eq(self.i.a),
                             tdiff.eq(ediffr),
                             self.o.a.eq(t_out),
                             self.o.a.s.eq(self.i.a.s), # whoops forgot sign
                            ]

        comb += self.o.ctx.eq(self.i.ctx)
        comb += self.o.z.eq(self.i.z)
        comb += self.o.out_do_z.eq(self.i.out_do_z)
        comb += self.o.oz.eq(self.i.oz)

        return m

