from nmigen import Module, Signal, Cat, Mux, Array, Const
from nmigen.cli import main, verilog

from fpbase import FPNumIn, FPNumOut, FPOp, Overflow, FPBase, FPState
from fpcommon.getop import FPGetOp


class FPMUL(FPBase):

    def __init__(self, width):
        FPBase.__init__(self)
        self.width = width

        self.in_a  = FPOp(width)
        self.in_b  = FPOp(width)
        self.out_z = FPOp(width)

    def get_fragment(self, platform=None):
        """ creates the HDL code-fragment for FPMUL
        """
        m = Module()

        # Latches
        a = FPNumIn(None, self.width, False)
        b = FPNumIn(None, self.width, False)
        z = FPNumOut(self.width, False)

        mw = (z.m_width)*2 - 1 + 3 # sticky/round/guard bits + (2*mant) - 1
        product = Signal(mw)

        of = Overflow()
        m.submodules.of = of
        m.submodules.a = a
        m.submodules.b = b
        m.submodules.z = z

        with m.FSM() as fsm:

            # ******
            # gets operand a

            with m.State("get_a"):
                self.get_op(m, self.in_a, a, "get_b")

            # ******
            # gets operand b

            with m.State("get_b"):
                self.get_op(m, self.in_b, b, "special_cases")

            # ******
            # special cases

            with m.State("special_cases"):
                #if a or b is NaN return NaN
                with m.If(a.is_nan | b.is_nan):
                    m.next = "put_z"
                    m.d.sync += z.nan(1)
                #if a is inf return inf
                with m.Elif(a.is_inf):
                    m.next = "put_z"
                    m.d.sync += z.inf(a.s ^ b.s)
                    #if b is zero return NaN
                    with m.If(b.is_zero):
                        m.d.sync += z.nan(1)
                #if b is inf return inf
                with m.Elif(b.is_inf):
                    m.next = "put_z"
                    m.d.sync += z.inf(a.s ^ b.s)
                    #if a is zero return NaN
                    with m.If(a.is_zero):
                        m.next = "put_z"
                        m.d.sync += z.nan(1)
                #if a is zero return zero
                with m.Elif(a.is_zero):
                    m.next = "put_z"
                    m.d.sync += z.zero(a.s ^ b.s)
                #if b is zero return zero
                with m.Elif(b.is_zero):
                    m.next = "put_z"
                    m.d.sync += z.zero(a.s ^ b.s)
                # Denormalised Number checks
                with m.Else():
                    m.next = "normalise_a"
                    self.denormalise(m, a)
                    self.denormalise(m, b)

            # ******
            # normalise_a

            with m.State("normalise_a"):
                self.op_normalise(m, a, "normalise_b")

            # ******
            # normalise_b

            with m.State("normalise_b"):
                self.op_normalise(m, b, "multiply_0")

            #multiply_0
            with m.State("multiply_0"):
                m.next = "multiply_1"
                m.d.sync += [
                   z.s.eq(a.s ^ b.s),
                   z.e.eq(a.e + b.e + 1),
                   product.eq(a.m * b.m * 4)
                ]

            #multiply_1
            with m.State("multiply_1"):
                mw = z.m_width
                m.next = "normalise_1"
                m.d.sync += [
                z.m.eq(product[mw+2:]),
                of.guard.eq(product[mw+1]),
                of.round_bit.eq(product[mw]),
                of.sticky.eq(product[0:mw] != 0)
            ]

            # ******
            # First stage of normalisation.
            with m.State("normalise_1"):
                self.normalise_1(m, z, of, "normalise_2")

            # ******
            # Second stage of normalisation.

            with m.State("normalise_2"):
                self.normalise_2(m, z, of, "round")

            # ******
            # rounding stage

            with m.State("round"):
                self.roundz(m, z, of.roundz)
                m.next = "corrections"

            # ******
            # correction stage

            with m.State("corrections"):
                self.corrections(m, z, "pack")

            # ******
            # pack stage
            with m.State("pack"):
                self.pack(m, z, "put_z")

            # ******
            # put_z stage

            with m.State("put_z"):
                self.put_z(m, z, self.out_z, "get_a")

        return m


if __name__ == "__main__":
    alu = FPMUL(width=32)
    main(alu, ports=alu.in_a.ports() + alu.in_b.ports() + alu.out_z.ports())
