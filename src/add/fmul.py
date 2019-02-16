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
        a = FPNum(self.width)
        b = FPNum(self.width)
        z = FPNum(self.width, 24)

        tot = Signal(28)     # sticky/round/guard bits, 23 result, 1 overflow

        of = Overflow()

        with m.FSM() as fsm:

        	with m.State("get_a"):
        		m.next += "get_b"
        		m.d.sync += s.in_a.ack.eq(1)
        		with m.If(s.in_a.ack & in_a.stb):
        			m.d.sync += [
        			a.eq(in_a),
        			s.in_a.ack(0)
        		]

"""
always @(posedge clk)
  begin

    case(state)

      get_a:
      begin
        s_input_a_ack <= 1;
        if (s_input_a_ack && input_a_stb) begin
          a <= input_a;
          s_input_a_ack <= 0;
          state <= get_b;
        end
      end

      get_b:
      begin
        s_input_b_ack <= 1;
        if (s_input_b_ack && input_b_stb) begin
          b <= input_b;
          s_input_b_ack <= 0;
          state <= unpack;
        end
      end

      unpack:
      begin
        a_m <= a[22 : 0];
        b_m <= b[22 : 0];
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
        s_output_z_stb <= 1;
        s_output_z <= z;
        if (s_output_z_stb && output_z_ack) begin
          s_output_z_stb <= 0;
          state <= get_a;
        end
      end

    endcase

    if (rst == 1) begin
      state <= get_a;
      s_input_a_ack <= 0;
      s_input_b_ack <= 0;
      s_output_z_stb <= 0;
    end
 end
 """