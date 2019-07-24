""" test of FPDIVMuxInOut
"""

from ieee754.fpdiv.pipeline import (FPDIVMuxInOut,)
from ieee754.fpcommon.test.fpmux import runfp

from sfpy import Float64, Float32, Float16

def rsqrt(x):
    return x.__class__(1.0) / x.sqrt()

def test_pipe_rsqrt_fp16():
    dut = FPDIVMuxInOut(16, 4)
    runfp(dut, 16, "test_fprsqrt_pipe_fp16", Float16, rsqrt,
          single_op=True, opcode=2, n_vals=100)

def test_pipe_rsqrt_fp32():
    dut = FPDIVMuxInOut(32, 4)
    runfp(dut, 32, "test_fprsqrt_pipe_fp32", Float32, rsqrt,
          single_op=True, opcode=2, n_vals=100)

def test_pipe_rsqrt_fp64():
    dut = FPDIVMuxInOut(64, 4)
    runfp(dut, 64, "test_fprsqrt_pipe_fp64", Float64, rsqrt,
          single_op=True, opcode=2, n_vals=100)

if __name__ == '__main__':
    test_pipe_rsqrt_fp32()
    test_pipe_rsqrt_fp16()
    test_pipe_rsqrt_fp64()
