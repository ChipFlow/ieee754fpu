"""IEEE Floating Point Divider

Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>
Copyright (C) 2019 Jacob Lifshay

Relevant bugreports:
* http://bugs.libre-riscv.org/show_bug.cgi?id=99
* http://bugs.libre-riscv.org/show_bug.cgi?id=43
* http://bugs.libre-riscv.org/show_bug.cgi?id=44
"""

from nmigen import Module, Signal, Cat
from nmigen.cli import main, verilog

from nmutil.pipemodbase import PipeModBase
from ieee754.fpcommon.postcalc import FPPostCalcData
from ieee754.div_rem_sqrt_rsqrt.div_pipe import DivPipeOutputData


class FPDivPostToFPFormat(PipeModBase):
    """ Last stage of div: preparation for normalisation.

        NOTE: this phase does NOT do ACTUAL DIV processing, it ONLY
        does "conversion" *out* of the Q/REM last stage
    """

    def __init__(self, pspec):
        super().__init__(pspec, "post_to_fp_fmt")

    def ispec(self):
        return DivPipeOutputData(self.pspec)  # Q/Rem in...

    def ospec(self):
        # XXX REQUIRED.  MUST NOT BE CHANGED.  this is the format
        # required for ongoing processing (normalisation, correction etc.)
        return FPPostCalcData(self.pspec)  # out to post-process

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        # copies sign and exponent and mantissa (mantissa and exponent to be
        # overridden below)
        comb += self.o.z.eq(self.i.z)

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

        with m.If(~self.i.out_do_z):
            # following section partially normalizes result to range [1.0, 2.0)
            fw = self.pspec.core_config.fract_width
            qr_int_part = Signal(2, reset_less=True)
            comb += qr_int_part.eq(self.i.quotient_root[fw:][:2])

            need_shift = Signal(reset_less=True)

            # shift left when result is less than 2.0 since result_m has 1 more
            # fraction bit, making assigning to it the equivalent of
            # dividing by 2.
            # this all comes out to:
            # if quotient_root < 2.0:
            #     # div by 2 from assign; mul by 2 from shift left
            #     result = (quotient_root * 2) / 2
            # else:
            #     # div by 2 from assign
            #     result = quotient_root / 2
            comb += need_shift.eq(qr_int_part < 2)

            # one extra fraction bit to accommodate the result when not
            # shifting and for effective div by 2
            result_m_fract_width = fw + 1
            # 1 integer bit since the numbers are less than 2.0
            result_m = Signal(1 + result_m_fract_width, reset_less=True)
            result_e = Signal(len(self.i.z.e), reset_less=True)

            comb += [
                result_m.eq(self.i.quotient_root << need_shift),
                result_e.eq(self.i.z.e + (1 - need_shift))
            ]

            # result_m is now in the range [1.0, 2.0)
            comb += [
                self.o.z.m.eq(result_m[3:]),             # mantissa
                self.o.of.m0.eq(result_m[3]),            # copy of mantissa LSB
                self.o.of.guard.eq(result_m[2]),         # guard
                self.o.of.round_bit.eq(result_m[1]),     # round
                self.o.of.sticky.eq(result_m[0] | self.i.remainder.bool()),
                self.o.z.e.eq(result_e),
            ]

        comb += self.o.out_do_z.eq(self.i.out_do_z)
        comb += self.o.oz.eq(self.i.oz)
        comb += self.o.ctx.eq(self.i.ctx)

        return m


