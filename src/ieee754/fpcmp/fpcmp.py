# IEEE Floating Point Conversion, FSGNJ
# Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>
# Copyright (C) 2020 Michael Nolan <mtnolan2640@gmail.com>


from nmigen import Module, Signal, Mux

from nmutil.pipemodbase import PipeModBase
from ieee754.fpcommon.basedata import FPBaseData
from ieee754.fpcommon.packdata import FPPackData
from ieee754.fpcommon.fpbase import FPNumDecode, FPNumBaseRecord


class FPCMPPipeMod(PipeModBase):
    """
    Floating point comparison: FEQ, FLT, FLE
    Opcodes (funct3):
       - 0b00 - FLE - floating point less than or equal to
       - 0b01 - FLT - floating point less than
       - 0b10 - FEQ - floating equals
    """
    def __init__(self, in_pspec):
        self.in_pspec = in_pspec
        super().__init__(in_pspec, "fpcmp")

    def ispec(self):
        return FPBaseData(self.in_pspec)

    def ospec(self):
        return FPPackData(self.in_pspec)

    def elaborate(self, platform):
        m = Module()

        # useful clarity variables
        comb = m.d.comb
        width = self.pspec.width
        opcode = self.i.ctx.op
        z1 = self.o.z

        a1 = FPNumBaseRecord(width, False)
        b1 = FPNumBaseRecord(width, False)
        m.submodules.sc_decode_a = a1 = FPNumDecode(None, a1)
        m.submodules.sc_decode_b = b1 = FPNumDecode(None, b1)

        m.d.comb += [a1.v.eq(self.i.a),
                     b1.v.eq(self.i.b)]

        both_zero = Signal()
        comb += both_zero.eq((a1.v[0:width-1] == 0) &
                             (b1.v[0:width-1] == 0))

        ab_equal = Signal()
        m.d.comb += ab_equal.eq((a1.v == b1.v) | both_zero)

        contains_nan = Signal()
        m.d.comb += contains_nan.eq(a1.is_nan | b1.is_nan)
        a_lt_b = Signal()

        # if(a1.is_zero && b1.is_zero):
        #    a_lt_b = 0
        # elif(a1.s != b1.s):
        #    a_lt_b = a1.s > b1.s (a is more negative than b)
        signs_same = Signal()
        comb += signs_same.eq(a1.s > b1.s)

        # else:  # a1.s == b1.s
        #    if(a1.s == 0):
        #         a_lt_b = a[0:31] < b[0:31]
        #    else:
        #         a_lt_b = a[0:31] > b[0:31]
        signs_different = Signal()
        comb += signs_different.eq(Mux(a1.s,
                                       (a1.v[0:width-1] > b1.v[0:width-1]),
                                       (a1.v[0:width-1] < b1.v[0:width-1])))

        comb += a_lt_b.eq(Mux(both_zero, 0,
                              Mux(a1.s == b1.s,
                              signs_different,
                              signs_same)))

        no_nan = Signal()
        # switch(opcode):
        #   case(0b00): # lt
        #       no_nan = a_lt_b
        #   case(0b01): # le
        #       no_nan = ab_equal
        #   case(0b10):
        #       no_nan = a_lt_b | ab_equal
        comb += no_nan.eq(
            Mux(opcode != 0b00, ab_equal, 0) |
            Mux(opcode[1], 0, a_lt_b))

        # if(a1.is_nan | b1.is_nan):
        #    z1 = 0
        # else:
        #    z1 = no_nan
        comb += z1.eq(Mux(contains_nan, 0, no_nan))

        # copy the context (muxid, operator)
        comb += self.o.ctx.eq(self.i.ctx)

        return m
