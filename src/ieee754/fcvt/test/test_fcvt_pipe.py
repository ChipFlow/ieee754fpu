""" test of FPCVTMuxInOut
"""

from ieee754.fcvt.pipeline import (FPCVTDownMuxInOut,)
from ieee754.fpcommon.test.fpmux import runfp

from sfpy import Float64, Float32, Float16

def fcvt_16(x):
    return Float16(x)

def fcvt_32(x):
    return Float32(x)

def test_down_pipe_fp32_16():
    dut = FPCVTDownMuxInOut(32, 16, 4)
    runfp(dut, 32, "test_fcvt_down_pipe_fp32_16", Float32, fcvt_16, True,
            n_vals=100)

def test_down_pipe_fp64_16():
    dut = FPCVTDownMuxInOut(64, 16, 4)
    runfp(dut, 64, "test_fcvt_down_pipe_fp64_16", Float64, fcvt_16, True,
            n_vals=100)

def test_down_pipe_fp64_32():
    dut = FPCVTDownMuxInOut(64, 32, 4)
    runfp(dut, 64, "test_fcvt_down_pipe_fp64_32", Float64, fcvt_32, True,
            n_vals=100)

if __name__ == '__main__':
    for i in range(200):
        test_down_pipe_fp64_16()
        test_down_pipe_fp32_16()
        test_down_pipe_fp64_32()

