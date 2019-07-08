""" test of FPADDMuxInOut
"""

from ieee754.fpadd.pipeline import (FPADDMuxInOut,)
from ieee754.fpcommon.test.fpmux import runfp, repeat
from ieee754.fpcommon.test.case_gen import get_corner_cases
from ieee754.fpcommon.test import unit_test_single
from ieee754.fpadd.test.add_data32 import regressions

from sfpy import Float32
from operator import add

def test_pipe_fp32_cornercases():
    dut = FPADDMuxInOut(32, 4)
    vals = repeat(dut.num_rows, get_corner_cases(unit_test_single))
    runfp(dut, 32, "test_fpadd_pipe_fp32_cornercases", Float32, add, vals=vals)

def test_pipe_fp32_regressions():
    dut = FPADDMuxInOut(32, 4)
    vals = repeat(dut.num_rows, regressions())
    runfp(dut, 32, "test_fpadd_pipe_fp32_regressions", Float32, add, vals=vals)

def test_pipe_fp32_rand():
    dut = FPADDMuxInOut(32, 4)
    runfp(dut, 32, "test_fpadd_pipe_fp32_rand", Float32, add)

if __name__ == '__main__':
    test_pipe_fp32_rand()
    test_pipe_fp32_regressions()
    test_pipe_fp32_cornercases()

