""" test of FPCVTMuxInOut
"""

from ieee754.fcvt.pipeline import (FPCVTUpMuxInOut,)
from ieee754.fpcommon.test.case_gen import run_pipe_fp
from ieee754.fpcommon.test import unit_test_single
from ieee754.fcvt.test.up_fcvt_data_32_64 import regressions

from sfpy import Float64, Float32

def fcvt_64(x):
    return Float64(x)

def test_pipe_fp32_64():
    dut = FPCVTUpMuxInOut(32, 64, 4)
    run_pipe_fp(dut, 32, "upfcvt", unit_test_single, Float32,
                regressions, fcvt_64, 10, True)

if __name__ == '__main__':
    test_pipe_fp32_64()

