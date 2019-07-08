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


def test_pipe_fp32_rand1():
    dut = FPADDMuxInOut(32, 4)
    pipe_cornercases_repeat(dut, "add_rand1", unit_test_single, Float32,
                                 32, get_rand1, corner_cases, add, 10)

def test_pipe_fp32_n127():
    dut = FPADDMuxInOut(32, 4)
    pipe_cornercases_repeat(dut, "add_n127", unit_test_single, Float32,
                                 32, get_n127, corner_cases, add, 10)

def test_pipe_fp32_nan_noncan():
    dut = FPADDMuxInOut(32, 4)
    pipe_cornercases_repeat(dut, "add_noncan", unit_test_single, Float32,
                                 32, get_nan_noncan, corner_cases, add, 10)

def test_pipe_fp32_nearly_zero():
    dut = FPADDMuxInOut(32, 4)
    pipe_cornercases_repeat(dut, "add_nearlyzero", unit_test_single, Float32,
                                 32, get_nearly_zero, corner_cases, add, 10)

def test_pipe_fp32_nearly_inf():
    dut = FPADDMuxInOut(32, 4)
    pipe_cornercases_repeat(dut, "add_nearlyinf", unit_test_single, Float32,
                                 32, get_nearly_inf, corner_cases, add, 10)

def test_pipe_fp32_corner_rand():
    dut = FPADDMuxInOut(32, 4)
    pipe_cornercases_repeat(dut, "add_corner_rand", unit_test_single, Float32,
                                 32, get_corner_rand, corner_cases, add, 10)

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
    test_pipe_fp32_regressions()
    test_pipe_fp32_cornercases()
    test_pipe_fp32_rand()
    test_pipe_fp32_rand1()
    test_pipe_fp32_nan_noncan()
    test_pipe_fp32_n127()
    test_pipe_fp32_nearly_zero()
    test_pipe_fp32_nearly_inf()
    test_pipe_fp32_corner_rand()

