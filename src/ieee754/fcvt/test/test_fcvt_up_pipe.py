""" test of FPCVTMuxInOut
"""

from ieee754.fcvt.pipeline import (FPCVTUpMuxInOut,)
from ieee754.fpcommon.test.fpmux import runfp

from sfpy import Float64, Float32, Float16

def fcvt_64(x):
    return Float64(x)

def fcvt_32(x):
    return Float32(x)

def test_down_pipe_fp16_32():
    dut = FPCVTUpMuxInOut(16, 32, 4)
    runfp(dut, 16, "test_fcvt_down_pipe_fp16_32", Float16, fcvt_32, True,
          n_vals=1000)

def test_down_pipe_fp16_64():
    dut = FPCVTUpMuxInOut(16, 64, 4)
    runfp(dut, 16, "test_fcvt_down_pipe_fp16_64", Float16, fcvt_64, True,
          n_vals=1000)

def test_down_pipe_fp32_64():
    dut = FPCVTUpMuxInOut(32, 64, 4)
    runfp(dut, 32, "test_fcvt_down_pipe_fp32_64", Float32, fcvt_64, True,
          n_vals=1000)

if __name__ == '__main__':
    test_down_pipe_fp16_32()
    test_down_pipe_fp16_64()
    test_down_pipe_fp32_64()

