""" test of FPCVTMuxInOut
"""

from ieee754.fcvt.pipeline import (FPCVTUpMuxInOut,)
from ieee754.fpcommon.test.case_gen import run_pipe_fp
from ieee754.fpcommon.test import unit_test_half
from ieee754.fcvt.test.up_fcvt_data_16_32 import regressions

from sfpy import Float32, Float16

def fcvt_32(x):
    return Float32(x)

def test_pipe_fp16_32():
    dut = FPCVTUpMuxInOut(16, 32, 4)
    run_pipe_fp(dut, 16, "upfcvt", unit_test_half, Float16,
                regressions, fcvt_32, 10, True)

if __name__ == '__main__':
    test_pipe_fp16_32()

