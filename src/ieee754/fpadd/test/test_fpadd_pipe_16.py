""" test of FPADDMuxInOut
"""

from ieee754.fpadd.pipeline import (FPADDMuxInOut,)
from ieee754.fpcommon.test.case_gen import run_pipe_fp
from ieee754.fpcommon.test import unit_test_half
from ieee754.fpadd.test.add_data16 import regressions

from sfpy import Float16
from operator import add


def test_pipe_fp16():
    dut = FPADDMuxInOut(16, 4)
    run_pipe_fp(dut, 16, "add", unit_test_half, Float16,
                   regressions, add, 10)


if __name__ == '__main__':
    test_pipe_fp16()
