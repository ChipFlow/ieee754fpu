""" test of FPMULMuxInOut
"""

from ieee754.fpmul.pipeline import (FPMULMuxInOut,)
from ieee754.fpcommon.test.fpmux import runfp

from sfpy import Float32, Float16
from operator import mul

def test_pipe_fp16():
    dut = FPMULMuxInOut(16, 4)
    runfp(dut, 16, "test_fpmul_pipe_fp16", Float16, mul)

def test_pipe_fp32():
    dut = FPMULMuxInOut(32, 4)
    runfp(dut, 32, "test_fpmul_pipe_fp32", Float32, mul)

if __name__ == '__main__':
    test_pipe_fp32()
