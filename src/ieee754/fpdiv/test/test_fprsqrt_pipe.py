""" test of FPDIVMuxInOut
"""

from ieee754.fpdiv.pipeline import (FPDIVMuxInOut,)
from ieee754.fpcommon.test.fpmux import runfp

import unittest
from sfpy import Float64, Float32, Float16


def rsqrt(x):
    # FIXME: switch to correct implementation (rounding once)
    return x.__class__(1.0) / x.sqrt()


class TestDivPipe(unittest.TestCase):
    def test_pipe_rsqrt_fp16(self):
        dut = FPDIVMuxInOut(16, 4)
        runfp(dut, 16, "test_fprsqrt_pipe_fp16", Float16, rsqrt,
              single_op=True, opcode=2, n_vals=100)

    def test_pipe_rsqrt_fp32(self):
        dut = FPDIVMuxInOut(32, 4)
        runfp(dut, 32, "test_fprsqrt_pipe_fp32", Float32, rsqrt,
              single_op=True, opcode=2, n_vals=100)

    def test_pipe_rsqrt_fp64(self):
        dut = FPDIVMuxInOut(64, 4)
        runfp(dut, 64, "test_fprsqrt_pipe_fp64", Float64, rsqrt,
              single_op=True, opcode=2, n_vals=100)


if __name__ == '__main__':
    unittest.main()
