""" test of FPCVTMuxInOut
"""

from ieee754.fcvt.pipeline import (FPCVTIntMuxInOut,)
from ieee754.fpcommon.test.fpmux import runfp

import sfpy
from sfpy import Float64, Float32, Float16

def to_uint16(x):
    return x

def to_uint32(x):
    return x

def fcvt_64(x):
    return sfpy.float.ui32_to_f64(x)

def fcvt_32(x):
    return sfpy.float.ui32_to_f32(x)

def test_int_pipe_fp16_32():
    dut = FPCVTIntMuxInOut(16, 32, 4)
    runfp(dut, 16, "test_fcvt_int_pipe_fp16_32", to_uint16, fcvt_32, True,
          n_vals=100)

def test_int_pipe_fp16_64():
    dut = FPCVTIntMuxInOut(16, 64, 4)
    runfp(dut, 16, "test_fcvt_int_pipe_fp16_64", to_uint16, fcvt_64, True,
          n_vals=100)

def test_int_pipe_fp32_64():
    dut = FPCVTIntMuxInOut(32, 64, 4)
    runfp(dut, 32, "test_fcvt_int_pipe_fp32_64", to_uint32, fcvt_64, True,
          n_vals=100)

if __name__ == '__main__':
    for i in range(200):
        test_int_pipe_fp16_32()
        test_int_pipe_fp16_64()
        test_int_pipe_fp32_64()

