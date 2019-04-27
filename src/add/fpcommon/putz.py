# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Signal
from nmigen.cli import main, verilog
from fpbase import FPState


class FPPutZ(FPState):

    def __init__(self, state, in_z, out_z, in_mid, out_mid, to_state=None):
        FPState.__init__(self, state)
        if to_state is None:
            to_state = "get_ops"
        self.to_state = to_state
        self.in_z = in_z
        self.out_z = out_z
        self.in_mid = in_mid
        self.out_mid = out_mid

    def action(self, m):
        if self.in_mid is not None:
            m.d.sync += self.out_mid.eq(self.in_mid)
        m.d.sync += [
          self.out_z.z.v.eq(self.in_z)
        ]
        with m.If(self.out_z.z.valid_o & self.out_z.z.ready_i_test):
            m.d.sync += self.out_z.z.valid_o.eq(0)
            m.next = self.to_state
        with m.Else():
            m.d.sync += self.out_z.z.valid_o.eq(1)


class FPPutZIdx(FPState):

    def __init__(self, state, in_z, out_zs, in_mid, to_state=None):
        FPState.__init__(self, state)
        if to_state is None:
            to_state = "get_ops"
        self.to_state = to_state
        self.in_z = in_z
        self.out_zs = out_zs
        self.in_mid = in_mid

    def action(self, m):
        outz_stb = Signal(reset_less=True)
        outz_ack = Signal(reset_less=True)
        m.d.comb += [outz_stb.eq(self.out_zs[self.in_mid].valid_o),
                     outz_ack.eq(self.out_zs[self.in_mid].ready_i_test),
                    ]
        m.d.sync += [
          self.out_zs[self.in_mid].v.eq(self.in_z.v)
        ]
        with m.If(outz_stb & outz_ack):
            m.d.sync += self.out_zs[self.in_mid].valid_o.eq(0)
            m.next = self.to_state
        with m.Else():
            m.d.sync += self.out_zs[self.in_mid].valid_o.eq(1)

