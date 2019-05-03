""" test of FPADDMuxInOut
"""

from ieee754.fpadd.pipeline import (FPADDMuxInOut,)
from ieee754.fpcommon.test.fpmux import runfp

from sfpy import Float64, Float32, Float16
from operator import add

def test_pipe_fp16():
    dut = FPADDMuxInOut(16, 4)
    runfp(dut, 16, "test_fpadd_pipe_fp16", Float16, add)

def test_pipe_fp32():
    dut = FPADDMuxInOut(32, 4)
    runfp(dut, 32, "test_fpadd_pipe_fp32", Float32, add)

def test_pipe_fp64():
    dut = FPADDMuxInOut(64, 4)
    runfp(dut, 64, "test_fpadd_pipe_fp64", Float64, add)

if __name__ == '__main__':
    test_pipe_fp16()
    test_pipe_fp32()
    test_pipe_fp64()

