""" test of FPMULMuxInOut
"""

from ieee754.fpmul.pipeline import (FPMULMuxInOut,)
from ieee754.fpcommon.test.case_gen import run_pipe_fp
from ieee754.fpcommon.test import unit_test_double
from ieee754.fpmul.test.mul_data64 import regressions

from sfpy import Float64
from operator import mul


def test_pipe_fp64():
    dut = FPMULMuxInOut(64, 4)
    run_pipe_fp(dut, 64, "mul", unit_test_double, Float64,
                   regressions, mul, 10)


if __name__ == '__main__':
    test_pipe_fp64()
