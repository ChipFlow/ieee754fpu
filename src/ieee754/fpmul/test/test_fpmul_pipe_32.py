""" test of FPMULMuxInOut
"""

from ieee754.fpmul.pipeline import (FPMULMuxInOut,)
from ieee754.fpcommon.test.case_gen import run_pipe_fp
from ieee754.fpcommon.test import unit_test_single
from ieee754.fpmul.test.mul_data32 import regressions

from sfpy import Float32
from operator import mul


def test_pipe_fp32():
    dut = FPMULMuxInOut(32, 4)
    run_pipe_fp(dut, 32, "mul", unit_test_single, Float32,
                   regressions, mul, 10)


if __name__ == '__main__':
    test_pipe_fp32()
