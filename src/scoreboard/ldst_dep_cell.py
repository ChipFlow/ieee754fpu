from nmigen.compat.sim import run_simulation
from nmigen.cli import verilog, rtlil
from nmigen import Module, Signal, Elaboratable
from nmutil.latch import SRLatch


class LDSTDepCell(Elaboratable):
    """ implements 11.4.12 mitch alsup load/store dependence cell, p45
    """
    def __init__(self):
        # inputs
        self.load_i = Signal(reset_less=True)     # load pending in (top)
        self.stor_i = Signal(reset_less=True)     # store pending in (top)
        self.issue_i = Signal(reset_less=True)    # Issue in (top)

        self.load_hit_i = Signal(reset_less=True) # load hit in (right)
        self.stwd_hit_i = Signal(reset_less=True) # store w/ data hit in (right)

        # outputs (latched rd/wr pend)
        self.ld_hold_st_o = Signal(reset_less=True) # load holds st out (left)
        self.st_hold_ld_o = Signal(reset_less=True) # st holds load out (left)

    def elaborate(self, platform):
        m = Module()
        m.submodules.war_l = war_l = SRLatch() # Write After Read Latch
        m.submodules.raw_l = raw_l = SRLatch() # Read After Write Latch

        i_s_l = Signal(reset_less=True)
        
        m.d.comb += i_s_l.eq(self.issue_i & self.stor_i & self.load_i)
        # write after read latch: loads block stores
        m.d.comb += war_l.s.eq(i_s_l)
        m.d.comb += war_l.r.eq(self.load_i)

        # read after write latch: stores block loads
        m.d.comb += raw_l.s.eq(i_s_l)
        m.d.comb += raw_l.r.eq(self.stor_i)

        # Hold results (read out horizontally)
        m.d.comb += self.ld_hold_st_o.eq(war_l.qn | self.load_hit_i)
        m.d.comb += self.st_hold_ld_o.eq(raw_l.qn | self.stwd_hit_i)

        return m

    def __iter__(self):
        yield self.load_i
        yield self.stor_i
        yield self.issue_i
        yield self.load_hit_i
        yield self.stwd_hit_i
        yield self.ld_hold_st_o
        yield self.st_hold_ld_o
                
    def ports(self):
        return list(self)


def dcell_sim(dut):
    yield dut.dest_i.eq(1)
    yield dut.issue_i.eq(1)
    yield
    yield dut.issue_i.eq(0)
    yield
    yield dut.src1_i.eq(1)
    yield dut.issue_i.eq(1)
    yield
    yield dut.issue_i.eq(0)
    yield
    yield dut.go_read_i.eq(1)
    yield
    yield dut.go_read_i.eq(0)
    yield
    yield dut.go_write_i.eq(1)
    yield
    yield dut.go_write_i.eq(0)
    yield

def test_dcell():
    dut = LDSTDepCell()
    vl = rtlil.convert(dut, ports=dut.ports())
    with open("test_ldst_dcell.il", "w") as f:
        f.write(vl)

    run_simulation(dut, dcell_sim(dut), vcd_name='test_ldst_dcell.vcd')

if __name__ == '__main__':
    test_dcell()
