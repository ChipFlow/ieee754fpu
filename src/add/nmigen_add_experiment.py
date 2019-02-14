# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal, Cat
from nmigen.cli import main

class FPNum:
    def __init__(self, width, m_width=None):
        self.width = width
        if m_width is None:
            m_width = width + 3
        self.v = Signal(width)      # Latched copy of value
        self.m = Signal(m_width)    # Mantissa: ??? seems to be 1 bit extra??
        self.e = Signal((10, True)) # Exponent: 10 bits, signed
        self.s = Signal()           # Sign bit


class FPADD:
    def __init__(self, width):
        self.width = width

        self.in_a     = Signal(width)
        self.in_a_stb = Signal()
        self.in_a_ack = Signal()

        self.in_b     = Signal(width)
        self.in_b_stb = Signal()
        self.in_b_ack = Signal()

        self.out_z     = Signal(width)
        self.out_z_stb = Signal()
        self.out_z_ack = Signal()

        s_out_z_stb  = Signal()
        s_out_z      = Signal(width)
        s_in_a_ack   = Signal()
        s_in_b_ack   = Signal()

    def create_z(self, z, s, e, m):
        return [
          z.v[31].eq(s),    # sign
          z.v[23:31].eq(e), # exp
          z.v[0:23].eq(m)   # mantissa
        ]

    def nan(self, z, s):
        return self.create_z(z, s, 0xff, 1<<22)

    def inf(self, z, s):
        return self.create_z(z, s, 0xff, 0)

    def get_fragment(self, platform):
        m = Module()

        # Latches
        a = FPNum(self.width)
        b = FPNum(self.width)
        z = FPNum(self.width, 24)

        # Sign
        a_s = Signal()
        b_s = Signal()
        z_s = Signal()

        guard = Signal()
        round_bit = Signal()
        sticky = Signal()

        tot = Signal(28)

        with m.FSM() as fsm:

            # ******
            # gets operand a

            with m.State("get_a"):
                with m.If((self.in_a_ack) & (self.in_a_stb)):
                    m.next = "get_b"
                    m.d.sync += [
                        a.v.eq(self.in_a),
                        self.in_a_ack.eq(0)
                    ]
                with m.Else():
                    m.d.sync += self.in_a_ack.eq(1)

            # ******
            # gets operand b

            with m.State("get_b"):
                with m.If((self.in_b_ack) & (self.in_b_stb)):
                    m.next = "get_a"
                    m.d.sync += [
                        b.v.eq(self.in_b),
                        self.in_b_ack.eq(0)
                    ]
                with m.Else():
                    m.d.sync += self.in_b_ack.eq(1)

            # ******
            # unpacks operands into sign, mantissa and exponent

            with m.State("unpack"):
                m.next = "special_cases"
                m.d.sync += [
                    # mantissa
                    a.m.eq(Cat(0, 0, 0, a.v[0:23])),
                    b.m.eq(Cat(0, 0, 0, b.v[0:23])),
                    # exponent (take off exponent bias, here)
                    a.e.eq(Cat(a.v[23:31]) - 127),
                    b.e.eq(Cat(b.v[23:31]) - 127),
                    # sign
                    a.s.eq(Cat(a.v[31])),
                    b.s.eq(Cat(b.v[31]))
                ]

            # ******
            # special cases: NaNs, infs, zeros, denormalised

            with m.State("special_cases"):

                # if a is NaN or b is NaN return NaN
                with m.If(((a.e == 128) & (a.m != 0)) | \
                          ((b.e == 128) & (b.m != 0))):
                    m.next = "put_z"
                    m.d.sync += self.nan(z, 1)

                # if a is inf return inf (or NaN)
                with m.Elif(a.e == 128):
                    m.next = "put_z"
                    m.d.sync += self.inf(z, a.s)
                    # if a is inf and signs don't match return NaN
                    with m.If((b.e == 128) & (a.s != b.s)):
                        m.d.sync += self.nan(z, b.s)

                # if b is inf return inf
                with m.Elif(b.e == 128):
                    m.next = "put_z"
                    m.d.sync += self.inf(z, b.s)

                # if a is zero and b zero return signed-a/b
                with m.Elif(((a.e == -127) & (a.m == 0)) & \
                            ((b.e == -127) & (b.m == 0))):
                    m.next = "put_z"
                    m.d.sync += self.create_z(z, a.s & b.s,
                                                 b.e[0:8] + 127,
                                                 b.m[3:26])

                # if a is zero return b
                with m.Elif((a.e == -127) & (a.m == 0)):
                    m.next = "put_z"
                    m.d.sync += self.create_z(z, b.s,
                                                 b.e[0:8] + 127,
                                                 b.m[3:26])

                # if b is zero return a
                with m.Elif((b.e == -127) & (b.m == 0)):
                    m.next = "put_z"
                    m.d.sync += self.create_z(z, a.s,
                                                 a.e[0:8] + 127,
                                                 a.m[3:26])

                # Denormalised Number checks
                with m.Else():
                    m.next = "align"
                    # denormalise a check
                    with m.If(a.e == -127):
                        m.d.sync += a.e.eq(-126) # limit a exponent
                    with m.Else():
                        m.d.sync += a.m[26].eq(1) # set highest mantissa bit
                    # denormalise b check
                    with m.If(b.e == -127):
                        m.d.sync += b.e.eq(-126) # limit b exponent
                    with m.Else():
                        m.d.sync += b.m[26].eq(1) # set highest mantissa bit

            # ******
            # align.  NOTE: this does *not* do single-cycle multi-shifting,
            #         it *STAYS* in the align state until the exponents match

            with m.State("align"):
                # exponent of a greater than b: increment b exp, shift b mant
                with m.If(a.e > b.e):
                    m.d.sync += [
                      b.e.eq(b.e + 1),
                      b.m.eq(b.m >> 1),
                      b.m[0].eq(b.m[0] | b.m[1]) # moo??
                    ]
                # exponent of b greater than a: increment a exp, shift a mant
                with m.Elif(a.e < b.e):
                    m.d.sync += [
                      a.e.eq(a.e + 1),
                      a.m.eq(a.m >> 1),
                      a.m[0].eq(a.m[0] | a.m[1]) # moo??
                    ]
                # exponents equal: move to next stage.
                with m.Else():
                    m.next = "add_0"

            # ******
            # First stage of add.  covers same-sign (add) and subtract
            # special-casing when mantissas are greater or equal, to
            # give greatest accuracy.

            with m.State("add_0"):
                m.next = "add_1"
                m.d.sync += z.e.eq(a.e)
                # same-sign (both negative or both positive) add mantissas
                with m.If(a.s == b.s):
                    m.d.sync += [
                        tot.eq(a.m + b.m),
                        z_s.eq(a.s)
                    ]
                # a mantissa greater than b, use a
                with m.Elif(a.m >= b.m):
                    m.d.sync += [
                        tot.eq(a.m - b.m),
                        z_s.eq(a.s)
                    ]
                # b mantissa greater than a, use b
                with m.Else():
                    m.d.sync += [
                        tot.eq(b.m - a.m),
                        z_s.eq(b.s)
                ]

            # ******
            # Second stage of add: preparation for normalisation.
            # detects when tot sum is too big (tot[27] is kinda a carry bit)

            with m.State("add_1"):
                m.next = "normalise_1"
                # tot[27] gets set when the sum overflows. shift result down
                with m.If(tot[27]):
                    m.d.sync += [
                        z.m.eq(tot[4:28]),
                        guard.eq(tot[3]),
                        round_bit.eq(tot[2]),
                        sticky.eq(tot[1] | tot[0]),
                        z.e.eq(z.e + 1)
                ]
                # tot[27] zero case
                with m.Else():
                    m.d.sync += [
                        z.m.eq(tot[3:27]),
                        guard.eq(tot[2]),
                        round_bit.eq(tot[1]),
                        sticky.eq(tot[0])
                ]

            # ******
            # First stage of normalisation.
            # NOTE: just like "align", this one keeps going round every clock
            #       until the result's exponent is within acceptable "range"
            # NOTE: the weirdness of reassigning guard and round is due to
            #       the extra mantissa bits coming from tot[0..2]

            with m.State("normalise_1"):
                with m.If((z.m[23] == 0) & (z.e > -126)):
                    m.d.sync +=[
                        z.e.eq(z.e - 1),  # DECREASE exponent
                        z.m.eq(z.m << 1), # shift mantissa UP
                        z.m[0].eq(guard), # steal guard bit (was tot[2])
                        guard.eq(round_bit), # steal round_bit (was tot[1])
                    ]
                with m.Else():
                    m.next = "normalize_2"

            # ******
            # Second stage of normalisation.
            # NOTE: just like "align", this one keeps going round every clock
            #       until the result's exponent is within acceptable "range"
            # NOTE: the weirdness of reassigning guard and round is due to
            #       the extra mantissa bits coming from tot[0..2]

            with m.State("normalise_2"):
                with m.If(z.e < -126):
                    m.d.sync +=[
                        z.e.eq(z.e + 1),  # INCREASE exponent
                        z.m.eq(z.m >> 1), # shift mantissa DOWN
                        guard.eq(z.m[0]),
                        round_bit.eq(guard),
                        sticky.eq(sticky | round_bit)
                    ]
                with m.Else():
                    m.next = "round"

            # ******
            # rounding stage

            with m.State("round"):
                m.next = "pack"
                with m.If(guard & (round_bit | sticky | z.m[0])):
                    m.d.sync += z.m.eq(z.m + 1) # mantissa rounds up
                    with m.If(z.m == 0xffffff): # all 1s
                        m.d.sync += z.e.eq(z.e + 1) # exponent rounds up

        return m

"""
  always @(posedge clk)
  begin

    case(state)

      get_a:
      begin
        s_in_a_ack <= 1;
        if (s_in_a_ack && in_a_stb) begin
          a <= in_a;
          s_in_a_ack <= 0;
          state <= get_b;
        end
      end

      get_b:
      begin
        s_in_b_ack <= 1;
        if (s_in_b_ack && in_b_stb) begin
          b <= in_b;
          s_in_b_ack <= 0;
          state <= unpack;
        end
      end

      unpack:
      begin
        a_m <= {a[22 : 0], 3'd0};
        b_m <= {b[22 : 0], 3'd0};
        a_e <= a[30 : 23] - 127;
        b_e <= b[30 : 23] - 127;
        a_s <= a[31];
        b_s <= b[31];
        state <= special_cases;
      end

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
          z[31] <= a_s;
          z[30:23] <= 255;
          z[22:0] <= 0;
          //if a is inf and signs don't match return nan
          if ((b_e == 128) && (a_s != b_s)) begin
              z[31] <= b_s;
              z[30:23] <= 255;
              z[22] <= 1;
              z[21:0] <= 0;
          end
          state <= put_z;
        //if b is inf return inf
        end else if (b_e == 128) begin
          z[31] <= b_s;
          z[30:23] <= 255;
          z[22:0] <= 0;
          state <= put_z;
        //if a is zero return b
        end else if ((($signed(a_e) == -127) && (a_m == 0)) && (($signed(b_e) == -127) && (b_m == 0))) begin
          z[31] <= a_s & b_s;
          z[30:23] <= b_e[7:0] + 127;
          z[22:0] <= b_m[26:3];
          state <= put_z;
        //if a is zero return b
        end else if (($signed(a_e) == -127) && (a_m == 0)) begin
          z[31] <= b_s;
          z[30:23] <= b_e[7:0] + 127;
          z[22:0] <= b_m[26:3];
          state <= put_z;
        //if b is zero return a
        end else if (($signed(b_e) == -127) && (b_m == 0)) begin
          z[31] <= a_s;
          z[30:23] <= a_e[7:0] + 127;
          z[22:0] <= a_m[26:3];
          state <= put_z;
        end else begin
          //Denormalised Number
          if ($signed(a_e) == -127) begin
            a_e <= -126;
          end else begin
            a_m[26] <= 1;
          end
          //Denormalised Number
          if ($signed(b_e) == -127) begin
            b_e <= -126;
          end else begin
            b_m[26] <= 1;
          end
          state <= align;
        end
      end

      align:
      begin
        if ($signed(a_e) > $signed(b_e)) begin
          b_e <= b_e + 1;
          b_m <= b_m >> 1;
          b_m[0] <= b_m[0] | b_m[1];
        end else if ($signed(a_e) < $signed(b_e)) begin
          a_e <= a_e + 1;
          a_m <= a_m >> 1;
          a_m[0] <= a_m[0] | a_m[1];
        end else begin
          state <= add_0;
        end
      end

      add_0:
      begin
        z_e <= a_e;
        if (a_s == b_s) begin
          tot <= a_m + b_m;
          z_s <= a_s;
        end else begin
          if (a_m >= b_m) begin
            tot <= a_m - b_m;
            z_s <= a_s;
          end else begin
            tot <= b_m - a_m;
            z_s <= b_s;
          end
        end
        state <= add_1;
      end

      add_1:
      begin
        if (tot[27]) begin
          z_m <= tot[27:4];
          guard <= tot[3];
          round_bit <= tot[2];
          sticky <= tot[1] | tot[0];
          z_e <= z_e + 1;
        end else begin
          z_m <= tot[26:3];
          guard <= tot[2];
          round_bit <= tot[1];
          sticky <= tot[0];
        end
        state <= normalise_1;
      end

      normalise_1:
      begin
        if (z_m[23] == 0 && $signed(z_e) > -126) begin
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
        if ($signed(z_e) == -126 && z_m[23:0] == 24'h0) begin
          z[31] <= 1'b0; // FIX SIGN BUG: -a + a = +0.
        end
        //if overflow occurs, return inf
        if ($signed(z_e) > 127) begin
          z[22 : 0] <= 0;
          z[30 : 23] <= 255;
          z[31] <= z_s;
        end
        state <= put_z;
      end

      put_z:
      begin
        s_out_z_stb <= 1;
        s_out_z <= z;
        if (s_out_z_stb && out_z_ack) begin
          s_out_z_stb <= 0;
          state <= get_a;
        end
      end

    endcase

    if (rst == 1) begin
      state <= get_a;
      s_in_a_ack <= 0;
      s_in_b_ack <= 0;
      s_out_z_stb <= 0;
    end

  end
  assign in_a_ack = s_in_a_ack;
  assign in_b_ack = s_in_b_ack;
  assign out_z_stb = s_out_z_stb;
  assign out_z = s_out_z;

endmodule
"""

if __name__ == "__main__":
    alu = FPADD(width=32)
    main(alu, ports=[
                    alu.in_a, alu.in_a_stb, alu.in_a_ack,
                    alu.in_b, alu.in_b_stb, alu.in_b_ack,
                    alu.out_z, alu.out_z_stb, alu.out_z_ack,
        ])
