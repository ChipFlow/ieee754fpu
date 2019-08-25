# IEEE Floating Point Conversion
# Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

from nmigen import Module, Signal, Cat, Mux
from nmigen.cli import main, verilog

from nmutil.pipemodbase import PipeModBase
from ieee754.fpcommon.basedata import FPBaseData
from ieee754.fpcommon.postcalc import FPPostCalcData
from ieee754.fpcommon.msbhigh import FPMSBHigh

from ieee754.fpcommon.fpbase import FPNumBaseRecord


class FPCVTIntToFloatMod(PipeModBase):
    """ FP integer conversion: copes with 16/32/64 int to 16/32/64 fp.

        self.ctx.i.op & 0x1 == 0x1 : SIGNED int
        self.ctx.i.op & 0x1 == 0x0 : UNSIGNED int
    """
    def __init__(self, in_pspec, out_pspec):
        self.in_pspec = in_pspec
        self.out_pspec = out_pspec
        super().__init__(in_pspec, "intconvert")

    def ispec(self):
        return FPBaseData(self.in_pspec)

    def ospec(self):
        return FPPostCalcData(self.out_pspec, e_extra=True)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        #m.submodules.sc_out_z = self.o.z

        # decode: XXX really should move to separate stage
        print("in_width out", self.in_pspec.width,
              self.out_pspec.width)
        print("a1", self.in_pspec.width)
        z1 = self.o.z
        a = self.i.a
        print("z1", z1.width, z1.rmw, z1.e_width, z1.e_start, z1.e_end)

        me = self.in_pspec.width
        mz = z1.rmw
        ms = mz - me
        print("ms-me", ms, me, mz)

        # 3 extra bits for guard/round/sticky
        msb = FPMSBHigh(me+3, z1.e_width)
        m.submodules.norm_msb = msb

        # signed or unsigned, use operator context
        signed = Signal(reset_less=True)
        comb += signed.eq(self.i.ctx.op[0])

        # mantissa (one less bit if signed), and sign
        mantissa = Signal(me, reset_less=True)
        sign = Signal(reset_less=True)

        # detect signed/unsigned.  key case: -ve numbers need inversion
        # to +ve because the FP sign says if it's -ve or not.
        comb += sign.eq(Mux(signed, a[-1], 0)) # sign in top bit of a
        comb += mantissa.eq(Mux(signed,
                                Mux(sign, -a,  # invert input if sign -ve
                                           a), # leave as-is
                                a))            # unsigned, use full a

        # set input from full INT
        comb += msb.m_in.eq(Cat(0, 0, 0, mantissa)) # g/r/s + input
        comb += msb.e_in.eq(me)                     # exp = int width

        # to do with FP16... not yet resolved why
        alternative = ms < 0

        if alternative:
            comb += z1.e.eq(msb.e_out-1)
            mmsb = msb.m_out[-mz-1:]
            if mz == 16:
                # larger int to smaller FP (uint32/64 -> fp16 most likely)
                comb += z1.m[ms-1:].eq(mmsb)
            else: # 32? XXX weirdness...
                comb += z1.m.eq(mmsb)
        else:
            # smaller int to larger FP
            comb += z1.e.eq(msb.e_out)
            comb += z1.m[ms:].eq(msb.m_out[3:])
        comb += z1.s.eq(sign)
        comb += z1.create(sign, z1.e, z1.m) # ... here

        # note: post-normalisation actually appears to be capable of
        # detecting overflow to infinity (FPPackMod).  so it's ok to
        # drop the bits into the mantissa (with a fixed exponent),
        # do some rounding (which might result in exceeding the
        # range of the target FP by re-increasing the exponent),
        # and basically *not* have to do any kind of range-checking
        # here: just set up guard/round/sticky, drop the INT into the
        # mantissa, and away we go.  XXX TODO: see if FPNormaliseMod
        # is even necessary.  it probably isn't

        # initialise rounding (but only activate if needed)
        if alternative:
            # larger int to smaller FP (uint32/64 -> fp16 most likely)
            comb += self.o.of.guard.eq(msb.m_out[-mz-2])
            comb += self.o.of.round_bit.eq(msb.m_out[-mz-3])
            comb += self.o.of.sticky.eq(msb.m_out[:-mz-3].bool())
            comb += self.o.of.m0.eq(msb.m_out[-mz-1])
        else:
            # smaller int to larger FP
            comb += self.o.of.guard.eq(msb.m_out[2])
            comb += self.o.of.round_bit.eq(msb.m_out[1])
            comb += self.o.of.sticky.eq(msb.m_out[:1].bool())
            comb += self.o.of.m0.eq(msb.m_out[3])

        a_nonzero = Signal(reset_less=True)
        comb += a_nonzero.eq(~a.bool())

        # prepare zero
        z_zero = FPNumBaseRecord(z1.width, False, name="z_zero")
        comb += z_zero.zero(0)

        # special cases?
        comb += self.o.out_do_z.eq(a_nonzero)

        # detect zero
        comb += self.o.oz.eq(Mux(a_nonzero, z1.v, z_zero.v))

        # copy the context (muxid, operator)
        comb += self.o.ctx.eq(self.i.ctx)

        return m


