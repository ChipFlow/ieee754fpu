from nmigen.compat.sim import run_simulation
from nmigen.cli import verilog, rtlil
from nmigen import Signal, Module, Elaboratable

""" jk latch

module jk(q,q1,j,k,c);
output q,q1;
input j,k,c;
reg q,q1;
initial begin q=1'b0; q1=1'b1; end
always @ (posedge c)
  begin
    case({j,k})
         {1'b0,1'b0}:begin q=q; q1=q1; end
         {1'b0,1'b1}: begin q=1'b0; q1=1'b1; end
         {1'b1,1'b0}:begin q=1'b1; q1=1'b0; end
         {1'b1,1'b1}: begin q=~q; q1=~q1; end
    endcase
   end
endmodule
"""

def latchregister(m, incoming, outgoing, settrue):
    reg = Signal.like(incoming) # make register same as input. reset is OK.
    with m.If(settrue):
        m.d.sync += reg.eq(incoming)      # latch input into register
        m.d.comb += outgoing.eq(incoming) # return input (combinatorial)
    with m.Else():
        m.d.comb += outgoing.eq(reg) # return input (combinatorial)


class SRLatch(Elaboratable):
    def __init__(self, sync=True):
        self.sync = sync
        self.s = Signal(reset=0)
        self.r = Signal(reset=1) # defaults to off
        self.q = Signal(reset_less=True)
        self.qn = Signal(reset_less=True)
        self.qlq = Signal()

    def elaborate(self, platform):
        m = Module()
        q_int = self.qlq

        if self.sync:
            with m.If(self.s):
                m.d.sync += q_int.eq(1)
            with m.Elif(self.r):
                m.d.sync += q_int.eq(0)
            with m.Else():
                m.d.sync += q_int.eq(q_int)
            m.d.comb += self.q.eq(q_int)
        else:
            with m.If(self.s):
                m.d.sync += q_int.eq(1)
                m.d.comb += self.q.eq(1)
            with m.Elif(self.r):
                m.d.sync += q_int.eq(0)
                m.d.comb += self.q.eq(0)
            with m.Else():
                m.d.sync += q_int.eq(q_int)
                m.d.comb += self.q.eq(q_int)
        m.d.comb += self.qn.eq(~self.q)

        return m

    def ports(self):
        return self.s, self.r, self.q, self.qn


def sr_sim(dut):
    yield dut.s.eq(0)
    yield dut.r.eq(0)
    yield
    yield
    yield
    yield dut.s.eq(1)
    yield
    yield
    yield
    yield dut.s.eq(0)
    yield
    yield
    yield
    yield dut.r.eq(1)
    yield
    yield
    yield
    yield dut.r.eq(0)
    yield
    yield
    yield

def test_sr():
    dut = SRLatch()
    vl = rtlil.convert(dut, ports=dut.ports())
    with open("test_srlatch.il", "w") as f:
        f.write(vl)

    run_simulation(dut, sr_sim(dut), vcd_name='test_srlatch.vcd')

    dut = SRLatch(sync=False)
    vl = rtlil.convert(dut, ports=dut.ports())
    with open("test_srlatch_async.il", "w") as f:
        f.write(vl)

    run_simulation(dut, sr_sim(dut), vcd_name='test_srlatch_async.vcd')

if __name__ == '__main__':
    test_sr()
