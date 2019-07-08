""" test of FPMULMuxInOut
"""

from ieee754.fpmul.pipeline import (FPMULMuxInOut,)
from ieee754.fpcommon.test.case_gen import run_pipe_fp
from ieee754.fpcommon.test import unit_test_half
from ieee754.fpmul.test.mul_data16 import regressions

from sfpy import Float16
from operator import mul


def test_pipe_fp16():
    dut = FPMULMuxInOut(16, 4)
    run_pipe_fp(dut, 16, "mul", unit_test_half, Float16,
                   regressions, mul, 10)


if __name__ == '__main__':
    test_pipe_fp16()
