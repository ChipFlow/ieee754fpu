""" key strategic example showing how to do multi-input fan-in into a
    multi-stage pipeline, then multi-output fanout.

    the multiplex ID from the fan-in is passed in to the pipeline, preserved,
    and used as a routing ID on the fanout.
"""

from random import randint
from math import log
from nmigen import Module, Signal, Cat, Value
from nmigen.compat.sim import run_simulation
from nmigen.cli import verilog, rtlil

from nmigen_add_experiment import (FPADDMuxInOut,)

from sfpy import Float32

class InputTest:
    def __init__(self, dut):
        self.dut = dut
        self.di = {}
        self.do = {}
        self.tlen = 10
        self.width = 32
        for mid in range(dut.num_rows):
            self.di[mid] = {}
            self.do[mid] = []
            for i in range(self.tlen):
                op1 = randint(0, (1<<self.width)-1)
                op2 = randint(0, (1<<self.width)-1)
                #op1 = 0x40900000
                #op2 = 0x40200000
                res = Float32(op1) + Float32(op2)
                self.di[mid][i] = (op1, op2)
                self.do[mid].append(res.bits)

    def send(self, mid):
        for i in range(self.tlen):
            op1, op2 = self.di[mid][i]
            rs = dut.p[mid]
            yield rs.i_valid.eq(1)
            yield rs.i_data.a.eq(op1)
            yield rs.i_data.b.eq(op2)
            yield rs.i_data.mid.eq(mid)
            yield
            o_p_ready = yield rs.o_ready
            while not o_p_ready:
                yield
                o_p_ready = yield rs.o_ready

            fop1 = Float32(op1)
            fop2 = Float32(op2)
            res = fop1 + fop2
            print ("send", mid, i, hex(op1), hex(op2), hex(res.bits),
                           fop1, fop2, res)

            yield rs.i_valid.eq(0)
            # wait random period of time before queueing another value
            for i in range(randint(0, 3)):
                yield

        yield rs.i_valid.eq(0)
        yield

        print ("send ended", mid)

        ## wait random period of time before queueing another value
        #for i in range(randint(0, 3)):
        #    yield

        #send_range = randint(0, 3)
        #if send_range == 0:
        #    send = True
        #else:
        #    send = randint(0, send_range) != 0

    def rcv(self, mid):
        while True:
            #stall_range = randint(0, 3)
            #for j in range(randint(1,10)):
            #    stall = randint(0, stall_range) != 0
            #    yield self.dut.n[0].i_ready.eq(stall)
            #    yield
            n = self.dut.n[mid]
            yield n.i_ready.eq(1)
            yield
            o_n_valid = yield n.o_valid
            i_n_ready = yield n.i_ready
            if not o_n_valid or not i_n_ready:
                continue

            out_mid = yield n.o_data.mid
            out_z = yield n.o_data.z

            out_i = 0

            print ("recv", out_mid, hex(out_z), "expected",
                        hex(self.do[mid][out_i] ))

            # see if this output has occurred already, delete it if it has
            assert mid == out_mid, "out_mid %d not correct %d" % (out_mid, mid)
            assert self.do[mid][out_i] == out_z
            del self.do[mid][out_i]

            # check if there's any more outputs
            if len(self.do[mid]) == 0:
                break
        print ("recv ended", mid)



if __name__ == '__main__':
    dut = FPADDMuxInOut(32, 2, 4)
    vl = rtlil.convert(dut, ports=dut.ports())
    with open("test_fpadd_pipe.il", "w") as f:
        f.write(vl)
    #run_simulation(dut, testbench(dut), vcd_name="test_inputgroup.vcd")

    test = InputTest(dut)
    run_simulation(dut, [test.rcv(1), test.rcv(0),
                         test.rcv(3), test.rcv(2),
                         test.send(0), test.send(1),
                         test.send(3), test.send(2),
                        ],
                   vcd_name="test_inoutmux_pipe.vcd")

