""" test of FPCVTMuxInOut
"""

from ieee754.fcvt.pipeline import (FPCVTMuxInOut,)
from ieee754.fpcommon.test.case_gen import run_pipe_fp
from ieee754.fpcommon.test import unit_test_single
from ieee754.fcvt.test.fcvt_data_32_16 import regressions

from sfpy import Float32, Float16

def fcvt_16(x):
    return Float16(x)

def test_pipe_fp32_16():
    dut = FPCVTMuxInOut(32, 16, 4)
    run_pipe_fp(dut, 32, "add", unit_test_single, Float32,
                regressions, fcvt_16, 10, True)

if __name__ == '__main__':
    test_pipe_fp32_16()

