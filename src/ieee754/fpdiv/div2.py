"""IEEE Floating Point Divider

Relevant bugreport: http://bugs.libre-riscv.org/show_bug.cgi?id=99
"""

from nmigen import Module, Signal, Elaboratable, Cat
from nmigen.cli import main, verilog

from ieee754.fpcommon.fpbase import FPState
from ieee754.fpcommon.postcalc import FPAddStage1Data
from ieee754.div_rem_sqrt_rsqrt.div_pipe import DivPipeOutputData


class FPDivStage2Mod(FPState, Elaboratable):
    """ Second stage of div: preparation for normalisation.
    """

    def __init__(self, pspec):
        self.pspec = pspec
        self.i = self.ispec()
        self.o = self.ospec()

    def ispec(self):
        return DivPipeOutputData(self.pspec)  # Q/Rem in...

    def ospec(self):
        # XXX REQUIRED.  MUST NOT BE CHANGED.  this is the format
        # required for ongoing processing (normalisation, correction etc.)
        return FPAddStage1Data(self.pspec)  # out to post-process

    def process(self, i):
        return self.o

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        m.submodules.div1 = self
        m.d.comb += self.i.eq(i)

    def elaborate(self, platform):
        m = Module()

        # copies sign and exponent and mantissa (mantissa and exponent to be
        # overridden below)
        m.d.comb += self.o.z.eq(self.i.z)

        # TODO: this is "phase 3" of divide (the very end of the pipeline)
        # takes the Q and R data (whatever) and performs
        # last-stage guard/round/sticky and copies mantissa into z.
        # post-processing stages take care of things from that point.

        # NOTE: this phase does NOT do ACTUAL DIV processing, it ONLY
        # does "conversion" *out* of the Q/REM last stage

        # Operations and input/output mantissa ranges:
        # fdiv:
        #   dividend [1.0, 2.0)
        #   divisor [1.0, 2.0)
        #   result (0.5, 2.0)
        #
        # fsqrt:
        #   radicand [1.0, 4.0)
        #   result [1.0, 2.0)
        #
        # frsqrt:
        #   radicand [1.0, 4.0)
        #   result (0.5, 1.0]

        # following section partially normalizes result to the range [1.0, 2.0)

        qr_int_part = Signal(2, reset_less=True)
        m.d.comb += qr_int_part.eq(
            self.i.quotient_root[self.pspec.core_config.fract_width:][:2])

        need_shift = Signal(reset_less=True)

        # shift left when result is less than 2.0 since result_m has 1 more
        # fraction bit, making assigning to it the equivalent of dividing by 2.
        # this all comes out to:
        # if quotient_root < 2.0:
        #     # div by 2 from assign; mul by 2 from shift left
        #     result = (quotient_root * 2) / 2
        # else:
        #     # div by 2 from assign
        #     result = quotient_root / 2
        m.d.comb += need_shift.eq(qr_int_part < 2)

        # one extra fraction bit to accommodate the result when not shifting
        # and for effective div by 2
        result_m_fract_width = self.pspec.core_config.fract_width + 1
        # 1 integer bit since the numbers are less than 2.0
        result_m = Signal(1 + result_m_fract_width, reset_less=True)
        result_e = Signal(len(self.i.z.e), reset_less=True)

        m.d.comb += [
            result_m.eq(self.i.quotient_root << need_shift),
            result_e.eq(self.i.z.e + (1 - need_shift))
        ]

        # result_m is now in the range [1.0, 2.0)

        # FIXME: below comment block out of date
        # NOTE: see FPDivStage0Mod comment.  the quotient is assumed
        # to be in the range 0.499999-recurring to 1.999998.  normalisation
        # will take care of that, *however*, it *might* be necessary to
        # subtract 1 from the exponent and have one extra bit in the
        # mantissa to compensate.  this is pretty much exactly what's
        # done in FPMUL, due to 0.5-0.9999 * 0.5-0.9999 also producing
        # values within the range 0.5 to 1.999998
        # FIXME: above comment block out of date

        with m.If(~self.i.out_do_z):  # FIXME: does this need to be conditional?
            m.d.comb += [
                self.o.z.m.eq(result_m[3:]),
                self.o.of.m0.eq(result_m[3]),  # copy of LSB
                self.o.of.guard.eq(result_m[2]),
                self.o.of.round_bit.eq(result_m[1]),
                self.o.of.sticky.eq(result_m[0] | self.i.remainder.bool()),
                self.o.z.e.eq(result_e),
            ]

        m.d.comb += self.o.out_do_z.eq(self.i.out_do_z)
        m.d.comb += self.o.oz.eq(self.i.oz)
        m.d.comb += self.o.ctx.eq(self.i.ctx)

        return m


class FPDivStage2(FPState):

    def __init__(self, pspec):
        FPState.__init__(self, "divider_1")
        self.mod = FPDivStage2Mod(pspec)
        self.out_z = FPNumBaseRecord(pspec, False)
        self.out_of = Overflow()
        self.norm_stb = Signal()

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, i)

        m.d.sync += self.norm_stb.eq(0)  # sets to zero when not in div1 state

        m.d.sync += self.out_of.eq(self.mod.out_of)
        m.d.sync += self.out_z.eq(self.mod.out_z)
        m.d.sync += self.norm_stb.eq(1)

    def action(self, m):
        m.next = "normalise_1"
