""" test of FPMULMuxInOut
"""

from ieee754.fpmul.pipeline import (FPMULMuxInOut,)
from ieee754.fpcommon.test.fpmux import runfp

from sfpy import Float64, Float32, Float16
from operator import mul

def test_pipe_fp16():
    dut = FPMULMuxInOut(16, 4)
    runfp(dut, 16, "test_fpmul_pipe_fp16", Float16, mul)

def test_pipe_fp32():
    dut = FPMULMuxInOut(32, 4)
    runfp(dut, 32, "test_fpmul_pipe_fp32", Float32, mul)

def test_pipe_fp64():
    dut = FPMULMuxInOut(64, 4)
    runfp(dut, 64, "test_fpmul_pipe_fp64", Float64, mul)

if __name__ == '__main__':
    # XXX BUG: 0xe7bb 0x81ce 0x2afa
    # XXX BUG: 0xe225 0x8181 0x249f -> 0x249e
    test_pipe_fp16()
    test_pipe_fp32()
    test_pipe_fp64()
