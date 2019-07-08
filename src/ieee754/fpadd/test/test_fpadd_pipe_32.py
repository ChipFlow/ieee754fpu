""" test of FPADDMuxInOut
"""

from ieee754.fpadd.pipeline import (FPADDMuxInOut,)
from ieee754.fpcommon.test.fpmux import runfp, repeat, pipe_cornercases_repeat
from ieee754.fpcommon.test.case_gen import get_corner_cases, corner_cases
from ieee754.fpcommon.test.case_gen import (get_rand1, get_nan_noncan,
                                            get_n127, get_nearly_zero,
                                            get_nearly_inf, get_corner_rand)
from ieee754.fpcommon.test import unit_test_single
from ieee754.fpadd.test.add_data32 import regressions

from sfpy import Float32
from operator import add


class PipeFPCase:
    def __init__(self, dut, name, mod, fmod, width, cc, fpfn, count):
        self.dut = dut
        self.name = name
        self.mod = mod
        self.fmod = fmod
        self.width = width
        self.cc = cc
        self.fpfn = fpfn
        self.count = count

    def run(self, name, fn):
        name = "%s_%s" % (self.name, name)
        pipe_cornercases_repeat(self.dut, name, self.mod, self.fmod,
                                self.width, fn, self.cc, self.fpfn,
                                self.count)

    def run_cornercases(self):
        vals = repeat(self.dut.num_rows, get_corner_cases(self.mod))
        tname = "test_fp%s_pipe_fp%d_cornercases" % (self.name, self.width)
        runfp(self.dut, self.width, tname, self.fmod, self.fpfn, vals=vals)

    def run_regressions(self, regressions_fn):
        vals = repeat(self.dut.num_rows, regressions_fn())
        tname = "test_fp%s_pipe_fp%d_regressions" % (self.name, self.width)
        runfp(self.dut, self.width, tname, self.fmod, self.fpfn, vals=vals)

    def run_random(self):
        tname = "test_fp%s_pipe_fp%d_rand" % (self.name, self.width)
        runfp(self.dut, self.width, tname, self.fmod, self.fpfn)


def test_pipe_fp32():
    dut = FPADDMuxInOut(32, 4)
    pc = PipeFPCase(dut, "add", unit_test_single, Float32,
                   32, corner_cases, add, 10)
    pc.run("rand1", get_rand1)
    pc.run("n127", get_n127)
    pc.run("noncan", get_nan_noncan)
    pc.run("nearlyzero", get_nearly_zero)
    pc.run("nearlyinf", get_nearly_inf)
    pc.run("corner_rand", get_corner_rand)
    pc.run_cornercases()
    pc.run_regressions(regressions)
    pc.run_random()


if __name__ == '__main__':
    test_pipe_fp32()
