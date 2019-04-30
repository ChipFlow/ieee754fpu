# IEEE Floating Point Divider (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal, Const, Cat, Elaboratable
from nmigen.cli import main, verilog, rtlil
from nmigen.compat.sim import run_simulation


from fpbase import FPNumIn, FPNumOut, FPOpIn, FPOpOut, FPBase, FPState
from nmoperator import eq
from singlepipe import SimpleHandshake, ControlBase
from test_buf_pipe import data_chain2, Test5


class FPDIV(FPBase, Elaboratable):

    def __init__(self, width):
        FPBase.__init__(self)
        self.width = width

        self.p = FPOpIn(width)
        self.n = FPOpOut(width)

        self.p.data_i = self.ispec()
        self.n.data_o = self.ospec()

        self.states = []

    def ispec(self):
        return Signal(self.width, name="a")

    def ospec(self):
        return Signal(self.width, name="z")

    def setup(self, m, i):
        m.d.comb += self.p.v.eq(i) # connect input

    def process(self, i):
        return self.n.v # return z output

    def add_state(self, state):
        self.states.append(state)
        return state

    def elaborate(self, platform=None):
        """ creates the HDL code-fragment for FPDiv
        """
        m = Module()

        # Latches
        a = FPNumIn(None, self.width, False)
        z = FPNumOut(self.width, False)

        m.submodules.p = self.p
        m.submodules.n = self.n
        m.submodules.a = a
        m.submodules.z = z

        m.d.comb += a.v.eq(self.p.v)

        with m.FSM() as fsm:

            # ******
            # gets operand a

            with m.State("get_a"):
                res = self.get_op(m, self.p, a, "add_1")
                m.d.sync += eq([a, self.p.ready_o], res)

            with m.State("add_1"):
                m.next = "pack"
                m.d.sync += [
                    z.s.eq(a.s), # sign
                    z.e.eq(a.e), # exponent
                    z.m.eq(a.m + 1), # mantissa
                ]

            # ******
            # pack stage

            with m.State("pack"):
                self.pack(m, z, "put_z")

            # ******
            # put_z stage

            with m.State("put_z"):
                self.put_z(m, z, self.n, "get_a")

        return m

class FPDIVPipe(ControlBase):

    def __init__(self, width):
        self.width = width
        self.fpdiv = FPDIV(width=width)
        ControlBase.__init__(self, self.fpdiv)

    def elaborate(self, platform):
        self.m = m = ControlBase.elaborate(self, platform)

        m.submodules.fpdiv = self.fpdiv

        # see if connecting to stb/ack works
        m.d.comb += self.fpdiv.p._connect_in(self.p)
        m.d.comb += self.fpdiv.n._connect_out(self.n, do_data=False)
        m.d.comb += self.n.data_o.eq(self.data_r)

        return m

def resultfn(data_o, expected, i, o):
    res = expected + 1
    assert data_o == res, \
                "%d-%d received data %x not match expected %x\n" \
                % (i, o, data_o, res)


if __name__ == "__main__":
    dut = FPDIVPipe(width=16)
    data = data_chain2()
    ports = dut.ports()
    vl = rtlil.convert(dut, ports=ports)
    with open("test_fsm_experiment.il", "w") as f:
        f.write(vl)
    test = Test5(dut, resultfn, data=data)
    run_simulation(dut, [test.send, test.rcv],
                    vcd_name="test_fsm_experiment.vcd")

