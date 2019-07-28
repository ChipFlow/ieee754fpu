""" test of FPDIVMuxInOut
"""

from ieee754.fpdiv.pipeline import (FPDIVMuxInOut,)
from ieee754.fpcommon.test.fpmux import runfp
from ieee754.div_rem_sqrt_rsqrt.core import DivPipeCoreOperation

import unittest
from sfpy import Float64, Float32, Float16


def rsqrt(x):
    # FIXME: switch to correct implementation
    # needs to use exact arithmetic and rounding only once at the end
    return x.__class__(float(Float64(1.0) / x.to_f64().sqrt()))


class TestDivPipe(unittest.TestCase):
    def test_pipe_rsqrt_fp16(self):
        dut = FPDIVMuxInOut(16, 4)
        # don't forget to initialize opcode; don't use magic numbers
        opcode = int(DivPipeCoreOperation.RSqrtRem)
        runfp(dut, 16, "test_fprsqrt_pipe_fp16", Float16, rsqrt,
              single_op=True, opcode=opcode, n_vals=100)

    def test_pipe_rsqrt_fp32(self):
        dut = FPDIVMuxInOut(32, 4)
        # don't forget to initialize opcode; don't use magic numbers
        opcode = int(DivPipeCoreOperation.RSqrtRem)
        runfp(dut, 32, "test_fprsqrt_pipe_fp32", Float32, rsqrt,
              single_op=True, opcode=opcode, n_vals=100)

    @unittest.skip("rsqrt not implemented for fp64")
    def test_pipe_rsqrt_fp64(self):
        dut = FPDIVMuxInOut(64, 4)
        # don't forget to initialize opcode; don't use magic numbers
        opcode = int(DivPipeCoreOperation.RSqrtRem)
        runfp(dut, 64, "test_fprsqrt_pipe_fp64", Float64, rsqrt,
              single_op=True, opcode=opcode, n_vals=100)


if __name__ == '__main__':
    unittest.main()
