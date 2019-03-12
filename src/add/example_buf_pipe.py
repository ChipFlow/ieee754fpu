""" nmigen implementation of buffered pipeline stage, based on zipcpu:
    https://zipcpu.com/blog/2017/08/14/strategies-for-pipelining.html
"""
from nmigen import Signal, Cat, Const, Mux, Module
from nmigen.compat.sim import run_simulation
from nmigen.cli import verilog, rtlil

class BufPipe:
    def __init__(self):
        # input
        self.i_p_stb = Signal()    # >>in - comes in from PREVIOUS stage
        self.i_n_busy = Signal()   # in<< - comes in from the NEXT stage
        self.i_data = Signal(32) # >>in - comes in from the PREVIOUS stage
        #self.i_rst = Signal()

        # buffered
        self.r_data = Signal(32)

        # output
        self.o_n_stb = Signal()    # out>> - goes out to the NEXT stage
        self.o_p_busy = Signal()   # <<out - goes out to the PREVIOUS stage
        self.o_data = Signal(32) # out>> - goes out to the NEXT stage

    def pre_process(self, d_in):
        return d_in

    def process(self, d_in):
        return d_in + 1

    def elaborate(self, platform):
        m = Module()

        i_p_stb_o_p_busyn = Signal(reset_less=True)
        m.d.comb += i_p_stb_o_p_busyn.eq(self.i_p_stb & (~self.o_p_busy))

        with m.If(~self.i_n_busy): # previous stage is not busy
            with m.If(~self.o_p_busy): # not stalled
                # nothing in buffer: send input direct to output
                m.d.sync += self.o_n_stb.eq(self.i_p_stb)
                m.d.sync += self.o_data.eq(self.process(self.i_data))
            with m.Else(): # o_p_busy is true, and something is in our buffer.
                # Flush the buffer to the output port.
                m.d.sync += self.o_n_stb.eq(1)
                m.d.sync += self.o_data.eq(self.r_data)
                # ignore input, since o_p_busy is also true.
            # also clear stall condition, declare register to be empty.
            m.d.sync += self.o_p_busy.eq(0)

        # (i_n_busy) is true here: previous stage is busy
        with m.Elif(~self.o_n_stb): # next stage being told "not busy"
            m.d.sync += self.o_n_stb.eq(self.i_p_stb)
            m.d.sync += self.o_p_busy.eq(0) # Keep the buffer empty
            # Apply the logic to the input data, and set the output data
            m.d.sync += self.o_data.eq(self.process(self.i_data))

        # (i_n_busy) and (o_n_stb) both true:
        with m.Elif(i_p_stb_o_p_busyn):
            # If next stage *is* busy, and not stalled yet, accept requested
            # input and store in temporary
            m.d.sync += self.o_p_busy.eq(self.i_p_stb & self.o_n_stb)
            with m.If(~self.o_n_stb):
                m.d.sync += self.r_data.eq(self.i_data)

        with m.If(~self.o_p_busy): # not stalled
            m.d.sync += self.r_data.eq(self.pre_process(self.i_data))

        return m

    def ports(self):
        return [self.i_p_stb, self.i_n_busy, self.i_data,
                self.r_data,
                self.o_n_stb, self.o_p_busy, self.o_data
               ]


def testbench(dut):
    yield dut.i_data.eq(5)
    yield dut.i_p_stb.eq(1)
    yield
    yield dut.i_data.eq(7)
    yield
    yield dut.i_data.eq(2)
    yield
    yield dut.i_n_busy.eq(1)
    yield dut.i_data.eq(9)
    yield
    yield dut.i_data.eq(12)
    yield
    yield dut.i_n_busy.eq(0)
    yield
    yield
    yield


if __name__ == '__main__':
    dut = BufPipe()
    vl = rtlil.convert(dut, ports=dut.ports())
    with open("test_bufpipe.il", "w") as f:
        f.write(vl)
    run_simulation(dut, testbench(dut), vcd_name="test_bufpipe.vcd")

