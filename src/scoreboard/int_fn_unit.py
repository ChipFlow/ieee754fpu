from nmigen.compat.sim import run_simulation
from nmigen.cli import verilog, rtlil
from nmigen import Module, Signal, Cat, Elaboratable
from nmutil.latch import SRLatch
from nmigen.lib.coding import Decoder


class IntFnUnit(Elaboratable):
    """ implements 11.4.8 integer function unit, p31
        also implements optional shadowing 11.5.1, p55

        shadowing can be used for branches as well as exceptions (interrupts),
        load/store hold (exceptions again), and vector-element predication
        (once the predicate is known, which it may not be at instruction issue)

        notes:

        * req_rel_i (request release) is the direct equivalent of pipeline
                    "output valid"
        * recover is a local python variable (actually go_die_o)
        * when shadow_wid = 0, recover and shadown are Consts
    """
    def __init__(self, wid, shadow_wid=0):
        self.reg_width = wid
        self.shadow_wid = shadow_wid

        # inputs
        self.dest_i = Signal(wid, reset_less=True) # Dest in (top)
        self.src1_i = Signal(wid, reset_less=True) # oper1 in (top)
        self.src2_i = Signal(wid, reset_less=True) # oper2 in (top)
        self.issue_i = Signal(reset_less=True)    # Issue in (top)

        self.go_write_i = Signal(reset_less=True) # Go Write in (left)
        self.go_read_i = Signal(reset_less=True)  # Go Read in (left)
        self.req_rel_i = Signal(wid, reset_less=True)  # request release (left)

        self.g_rd_pend_i = Signal(wid, reset_less=True)  # global rd (right)
        self.g_wr_pend_i = Signal(wid, reset_less=True)  # global wr (right)

        if shadow_wid:
            self.shadow_i = Signal(shadow_wid, reset_less=True)
            self.s_fail_i  = Signal(shadow_wid, reset_less=True)
            self.s_good_i  = Signal(shadow_wid, reset_less=True)
            self.go_die_o  = Signal(reset_less=True)

        # outputs
        self.readable_o = Signal(reset_less=True) # Readable out (right)
        self.writable_o = Signal(reset_less=True) # Writable out (right)
        self.busy_o = Signal(reset_less=True) # busy out (left)

        self.rd_pend_o = Signal(wid, reset_less=True) # rd pending (right)
        self.wr_pend_o = Signal(wid, reset_less=True) # wr pending (right)

    def elaborate(self, platform):
        m = Module()
        m.submodules.rd_l = rd_l = SRLatch(sync=False)
        m.submodules.wr_l = wr_l = SRLatch(sync=False)
        m.submodules.dest_d = dest_d = Decoder(self.reg_width)
        m.submodules.src1_d = src1_d = Decoder(self.reg_width)
        m.submodules.src2_d = src2_d = Decoder(self.reg_width)
        s_latches = []
        for i in range(self.shadow_wid):
            sl = SRLatch(sync=False)
            setattr(m.submodules, "shadow%d" % i, sl)
            s_latches.append(sl)

        # shadow / recover (optional: shadow_wid > 0)
        if self.shadow_wid:
            recover = self.go_die_o
            si = Signal(self.shadow_wid, reset_less=True)
            sq = Signal(self.shadow_wid, reset_less=True)
            shadown = Signal(reset_less=True)
            recfail = Signal(self.shadow_wid, reset_less=True)
            l = self.shadow_i  & Cat(*([self.issue_i] * self.shadow_wid))
            q_l = []
            for i, s in enumerate(l):
                m.d.comb += s_latches[i].s.eq(s)  # issue_i & shadow_i[i]
                m.d.comb += s_latches[i].r.eq(self.s_good_i[i])
                q_l.append(s_latches[i].q)
            m.d.comb += sq.eq(Cat(*q_l))
            m.d.comb += shadown.eq(~sq.bool())
            m.d.comb += recfail.eq(sq & self.s_fail_i)
            m.d.comb += recover.eq(recfail.bool())
        else:
            shadown = Const(1)
            recover = Const(0)

        # go_write latch: reset on go_write HI, set on issue
        m.d.comb += wr_l.s.eq(self.issue_i)
        m.d.comb += wr_l.r.eq(self.go_write_i | recover)

        # src1 latch: reset on go_read HI, set on issue
        m.d.comb += rd_l.s.eq(self.issue_i)
        m.d.comb += rd_l.r.eq(self.go_read_i | recover)

        # dest decoder: write-pending out
        m.d.comb += dest_d.i.eq(self.dest_i)
        m.d.comb += dest_d.n.eq(wr_l.qn) # decode is inverted
        m.d.comb += self.busy_o.eq(wr_l.q) # busy if set
        m.d.comb += self.wr_pend_o.eq(dest_d.o)

        # src1/src2 decoder: read-pending out
        m.d.comb += src1_d.i.eq(self.src1_i)
        m.d.comb += src1_d.n.eq(rd_l.qn) # decode is inverted
        m.d.comb += src2_d.i.eq(self.src2_i)
        m.d.comb += src2_d.n.eq(rd_l.qn) # decode is inverted
        m.d.comb += self.rd_pend_o.eq(src1_d.o | src2_d.o)

        # readable output signal
        int_g_wr = Signal(self.reg_width, reset_less=True)
        m.d.comb += int_g_wr.eq(self.g_wr_pend_i & self.rd_pend_o)
        m.d.comb += self.readable_o.eq(int_g_wr.bool())

        # writable output signal
        int_g_rw = Signal(self.reg_width, reset_less=True)
        g_rw = Signal(reset_less=True)
        m.d.comb += int_g_rw.eq(self.g_rd_pend_i & self.wr_pend_o)
        m.d.comb += g_rw.eq(~int_g_rw.bool())
        m.d.comb += self.writable_o.eq(g_rw & rd_l.q & self.req_rel_i & shadown)

        return m

    def __iter__(self):
        yield self.dest_i
        yield self.src1_i
        yield self.src2_i
        yield self.issue_i
        yield self.go_write_i
        yield self.go_read_i
        yield self.req_rel_i
        yield self.g_rd_pend_i
        yield self.g_wr_pend_i
        yield self.readable_o
        yield self.writable_o
        yield self.rd_pend_o
        yield self.wr_pend_o

    def ports(self):
        return list(self)


def int_fn_unit_sim(dut):
    yield dut.dest_i.eq(1)
    yield dut.issue_i.eq(1)
    yield
    yield dut.issue_i.eq(0)
    yield
    yield dut.src1_i.eq(1)
    yield dut.issue_i.eq(1)
    yield
    yield
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

def test_int_fn_unit():
    dut = IntFnUnit(32, 2)
    vl = rtlil.convert(dut, ports=dut.ports())
    with open("test_int_fn_unit.il", "w") as f:
        f.write(vl)

    run_simulation(dut, int_fn_unit_sim(dut), vcd_name='test_int_fn_unit.vcd')

if __name__ == '__main__':
    test_int_fn_unit()
