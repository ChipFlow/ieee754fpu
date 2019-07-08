""" test of FPADDMuxInOut
"""

from ieee754.fpadd.pipeline import (FPADDMuxInOut,)
from ieee754.fpcommon.test.case_gen import run_pipe_fp
from ieee754.fpcommon.test import unit_test_double
from ieee754.fpadd.test.add_data64 import regressions

from sfpy import Float64
from operator import add


def test_pipe_fp64():
    dut = FPADDMuxInOut(64, 4)
    run_pipe_fp(dut, 64, "add", unit_test_double, Float64,
                   regressions, add, 10)


if __name__ == '__main__':
    test_pipe_fp64()
