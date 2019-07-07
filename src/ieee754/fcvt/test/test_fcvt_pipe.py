""" test of FPCVTMuxInOut
"""

from ieee754.fcvt.pipeline import (FPCVTMuxInOut,)
from ieee754.fpcommon.test.fpmux import runfp

from sfpy import Float64, Float32, Float16

def fcvt_16(x):
    return Float16(x)

def fcvt_32(x):
    return Float32(x)

def test_pipe_fp32_16():
    dut = FPCVTMuxInOut(32, 16, 4)
    runfp(dut, 32, "test_fcvt_pipe_fp32_16", Float32, fcvt_16, True)

def test_pipe_fp64_16():
    dut = FPCVTMuxInOut(64, 16, 4)
    runfp(dut, 64, "test_fcvt_pipe_fp64_16", Float64, fcvt_16, True)

def test_pipe_fp64_32():
    dut = FPCVTMuxInOut(64, 32, 4)
    runfp(dut, 64, "test_fcvt_pipe_fp64_32", Float64, fcvt_32, True)

if __name__ == '__main__':
    test_pipe_fp64_16()
    test_pipe_fp32_16()
    test_pipe_fp64_32()

