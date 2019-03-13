""" nmigen implementation of buffered pipeline stage, based on zipcpu:
    https://zipcpu.com/blog/2017/08/14/strategies-for-pipelining.html
"""
from nmigen import Signal, Cat, Const, Mux, Module
from nmigen.compat.sim import run_simulation
from nmigen.cli import verilog, rtlil

class BufPipe:
    """ buffered pipeline stage

        stage-1   i_p_stb  >>in   stage   o_n_stb  out>>   stage+1
        stage-1   o_p_busy <<out  stage   i_n_busy <<in    stage+1
        stage-1   i_data   >>in   stage   o_data   out>>   stage+1
                              |             |
                              +------->  process
                              |             |
                              +-- r_data ---+
    """
    def __init__(self):
        # input
        #self.i_p_rst = Signal()    # >>in - comes in from PREVIOUS stage
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
        return d_in | 0xf0000

    def process(self, d_in):
        return d_in + 1

    def elaborate(self, platform):
        m = Module()

        o_p_busyn = Signal(reset_less=True)
        i_p_stb_o_p_busyn = Signal(reset_less=True)
        m.d.comb += o_p_busyn.eq(~self.o_p_busy)
        m.d.comb += i_p_stb_o_p_busyn.eq(self.i_p_stb & o_p_busyn)

        result = Signal(32)
        m.d.comb += result.eq(self.process(self.i_data))
        with m.If(o_p_busyn): # not stalled
            m.d.sync += self.r_data.eq(result)

        #with m.If(self.i_p_rst): # reset
        #    m.d.sync += self.o_n_stb.eq(0)
        #    m.d.sync += self.o_p_busy.eq(0)
        with m.If(~self.i_n_busy): # previous stage is not busy
            with m.If(o_p_busyn): # not stalled
                # nothing in buffer: send input direct to output
                m.d.sync += self.o_n_stb.eq(self.i_p_stb)
                m.d.sync += self.o_data.eq(result)
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
            m.d.sync += self.o_data.eq(result)

        # (i_n_busy) and (o_n_stb) both true:
        with m.Elif(i_p_stb_o_p_busyn):
            # If next stage *is* busy, and not stalled yet, accept input
            m.d.sync += self.o_p_busy.eq(self.i_p_stb & self.o_n_stb)

        with m.If(o_p_busyn): # not stalled
            # turns out that from all of the above conditions, just
            # always put result into buffer if not busy
            m.d.sync += self.r_data.eq(result)

        return m

    def ports(self):
        return [self.i_p_stb, self.i_n_busy, self.i_data,
                self.r_data,
                self.o_n_stb, self.o_p_busy, self.o_data
               ]


def testbench(dut):
    #yield dut.i_p_rst.eq(1)
    yield dut.i_n_busy.eq(1)
    yield dut.o_p_busy.eq(1)
    yield
    yield
    #yield dut.i_p_rst.eq(0)
    yield dut.i_n_busy.eq(0)
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
    yield dut.i_p_stb.eq(0)
    yield dut.i_data.eq(12)
    yield
    yield dut.i_data.eq(32)
    yield dut.i_n_busy.eq(0)
    yield
    yield
    yield
    yield


if __name__ == '__main__':
    dut = BufPipe()
    vl = rtlil.convert(dut, ports=dut.ports())
    with open("test_bufpipe.il", "w") as f:
        f.write(vl)
    run_simulation(dut, testbench(dut), vcd_name="test_bufpipe.vcd")

