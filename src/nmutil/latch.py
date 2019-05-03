from nmigen.compat.sim import run_simulation
from nmigen.cli import verilog, rtlil
from nmigen import Signal, Module, Elaboratable


class SRLatch(Elaboratable):
    def __init__(self):
        self.s = Signal(reset_less=True)
        self.r = Signal(reset_less=True)
        self.q = Signal(reset_less=True)
        self.qn = Signal(reset_less=True)

    def elaborate(self, platform):
        m = Module()
        q_int = Signal(reset_less=True)
        qn_int = Signal(reset_less=True)

        m.d.comb += self.q.eq(~(self.s | qn_int))
        m.d.comb += self.qn.eq(~(self.r | q_int))

        m.d.sync += q_int.eq(self.q)
        m.d.sync += qn_int.eq(self.qn)

        return m

    def ports(self):
        return self.s, self.r, self.q, self.qn


def sr_sim(dut):
    yield dut.s.eq(0)
    yield dut.r.eq(0)
    yield
    yield dut.s.eq(1)
    yield
    yield dut.s.eq(0)
    yield
    yield dut.r.eq(1)
    yield
    yield dut.r.eq(0)
    yield
    yield

def test_sr():
    dut = SRLatch()
    vl = rtlil.convert(dut, ports=dut.ports())
    with open("test_srlatch.il", "w") as f:
        f.write(vl)

    run_simulation(dut, sr_sim(dut), vcd_name='test_srlatch.vcd')

if __name__ == '__main__':
    test_sr()
