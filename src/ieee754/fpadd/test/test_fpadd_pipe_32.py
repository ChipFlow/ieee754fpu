""" test of FPADDMuxInOut
"""

from ieee754.fpadd.pipeline import (FPADDMuxInOut,)
from ieee754.fpcommon.test.case_gen import run_pipe_fp
from ieee754.fpcommon.test import unit_test_single
from ieee754.fpadd.test.add_data32 import regressions

from sfpy import Float32
from operator import add


def test_pipe_fp32():
    dut = FPADDMuxInOut(32, 4)
    run_pipe_fp(dut, 32, "add", unit_test_single, Float32,
                   regressions, add, 10)


if __name__ == '__main__':
    test_pipe_fp32()
