from nmigen import Module, Signal
from nmigen.cli import main, verilog

from fpbase import FPNum, FPOp, Overflow, FPBase


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
        a = FPNum(self.width, False)
        b = FPNum(self.width, False)
        z = FPNum(self.width, False)

        mw = (z.m_width)*2 - 1 + 3 # sticky/round/guard bits + (2*mant) - 1
        product = Signal(mw)

        of = Overflow()

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
                with m.If(a.is_nan() | b.is_nan()):
                    m.next = "put_z"
                    m.d.sync += z.nan(1)
                #if a is inf return inf
                with m.Elif(a.is_inf()):
                    m.next = "put_z"
                    m.d.sync += z.inf(a.s ^ b.s)
                    #if b is zero return NaN
                    with m.If(b.is_zero()):
                        m.d.sync += z.nan(1)
                #if b is inf return inf
                with m.Elif(b.is_inf()):
                    m.next = "put_z"
                    m.d.sync += z.inf(a.s ^ b.s)
                    #if a is zero return NaN
                    with m.If(a.is_zero()):
                        m.next = "put_z"
                        m.d.sync += z.nan(1)
                #if a is zero return zero
                with m.Elif(a.is_zero()):
                    m.next = "put_z"
                    m.d.sync += z.zero(a.s ^ b.s)
                #if b is zero return zero
                with m.Elif(b.is_zero()):
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
                self.roundz(m, z, of, "corrections")

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

"""
special_cases:
      begin
        //if a is NaN or b is NaN return NaN
        if ((a_e == 128 && a_m != 0) || (b_e == 128 && b_m != 0)) begin
          z[31] <= 1;
          z[30:23] <= 255;
          z[22] <= 1;
          z[21:0] <= 0;
          state <= put_z;
        //if a is inf return inf
        end else if (a_e == 128) begin
          z[31] <= a_s ^ b_s;
          z[30:23] <= 255;
          z[22:0] <= 0;
          //if b is zero return NaN
          if (($signed(b_e) == -127) && (b_m == 0)) begin
            z[31] <= 1;
            z[30:23] <= 255;
            z[22] <= 1;
            z[21:0] <= 0;
          end
          state <= put_z;
        //if b is inf return inf
        end else if (b_e == 128) begin
          z[31] <= a_s ^ b_s;
          z[30:23] <= 255;
          z[22:0] <= 0;
          //if a is zero return NaN
          if (($signed(a_e) == -127) && (a_m == 0)) begin
            z[31] <= 1;
            z[30:23] <= 255;
            z[22] <= 1;
            z[21:0] <= 0;
          end
          state <= put_z;
        //if a is zero return zero
        end else if (($signed(a_e) == -127) && (a_m == 0)) begin
          z[31] <= a_s ^ b_s;
          z[30:23] <= 0;
          z[22:0] <= 0;
          state <= put_z;
        //if b is zero return zero
        end else if (($signed(b_e) == -127) && (b_m == 0)) begin
          z[31] <= a_s ^ b_s;
          z[30:23] <= 0;
          z[22:0] <= 0;
          state <= put_z;
          //^ done up to here
        end else begin
          //Denormalised Number
          if ($signed(a_e) == -127) begin
            a_e <= -126;
          end else begin
            a_m[23] <= 1;
          end
          //Denormalised Number
          if ($signed(b_e) == -127) begin
            b_e <= -126;
          end else begin
            b_m[23] <= 1;
          end
          state <= normalise_a;
        end
      end

      normalise_a:
      begin
        if (a_m[23]) begin
          state <= normalise_b;
        end else begin
          a_m <= a_m << 1;
          a_e <= a_e - 1;
        end
      end

      normalise_b:
      begin
        if (b_m[23]) begin
          state <= multiply_0;
        end else begin
          b_m <= b_m << 1;
          b_e <= b_e - 1;
        end
      end

      multiply_0:
      begin
        z_s <= a_s ^ b_s;
        z_e <= a_e + b_e + 1;
        product <= a_m * b_m * 4;
        state <= multiply_1;
      end

      multiply_1:
      begin
        z_m <= product[49:26];
        guard <= product[25];
        round_bit <= product[24];
        sticky <= (product[23:0] != 0);
        state <= normalise_1;
      end

      normalise_1:
      begin
        if (z_m[23] == 0) begin
          z_e <= z_e - 1;
          z_m <= z_m << 1;
          z_m[0] <= guard;
          guard <= round_bit;
          round_bit <= 0;
        end else begin
          state <= normalise_2;
        end
      end

      normalise_2:
      begin
        if ($signed(z_e) < -126) begin
          z_e <= z_e + 1;
          z_m <= z_m >> 1;
          guard <= z_m[0];
          round_bit <= guard;
          sticky <= sticky | round_bit;
        end else begin
          state <= round;
        end
      end

      round:
      begin
        if (guard && (round_bit | sticky | z_m[0])) begin
          z_m <= z_m + 1;
          if (z_m == 24'hffffff) begin
            z_e <=z_e + 1;
          end
        end
        state <= pack;
      end

      pack:
      begin
        z[22 : 0] <= z_m[22:0];
        z[30 : 23] <= z_e[7:0] + 127;
        z[31] <= z_s;
        if ($signed(z_e) == -126 && z_m[23] == 0) begin
          z[30 : 23] <= 0;
        end
        //if overflow occur
        s, return inf
        if ($signed(z_e) > 127) begin
          z[22 : 0] <= 0;
          z[30 : 23] <= 255;
          z[31] <= z_s;
        end
        state <= put_z;
      end

      put_z:
      begin
        s_output_z_stb <= 1;
        s_output_z <= z;
        if (s_output_z_stb && output_z_ack) begin
          s_output_z_stb <= 0;
          state <= get_a;
        end
end

"""

if __name__ == "__main__":
    alu = FPMUL(width=32)
    main(alu, ports=alu.in_a.ports() + alu.in_b.ports() + alu.out_z.ports())
