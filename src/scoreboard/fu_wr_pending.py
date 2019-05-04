from nmigen import Elaboratable, Module, Signal


class FUReadWritePending(Elaboratable):
    def __init__(self, reg_count):
        self.reg_count = reg_count
        self.dest_fwd_i = Signal(fu_count, reset_less=True)
        self.src1_fwd_i = Signal(fu_count, reset_less=True)
        self.src2_fwd_i = Signal(fu_count, reset_less=True)

        self.wr_pend_o = Signal(reset_less=True)
        self.rd_pend_o = Signal(reset_less=True)

    def elaboratable(self, platform):
        m = Module()
        srces = Cat(self.src1_fwd_i, self.src2_fwd_i)
        m.d.comb += self.wr_pend_o.eq(self.dest_fwd_i.bool())
        m.d.comb += self.rd_pend_o.eq(srces.bool() 
        return m

