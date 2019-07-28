""" test of FPDIVMuxInOut
"""

from ieee754.fpdiv.pipeline import (FPDIVMuxInOut,)
from ieee754.fpcommon.test.fpmux import runfp
from ieee754.div_rem_sqrt_rsqrt.core import DivPipeCoreOperation

import unittest
from sfpy import Float64, Float32, Float16
from operator import truediv as div


class TestDivPipe(unittest.TestCase):
    def test_pipe_div_fp16(self):
        dut = FPDIVMuxInOut(16, 4)
        # don't forget to initialize opcode; don't use magic numbers
        opcode = int(DivPipeCoreOperation.UDivRem)
        runfp(dut, 16, "test_fpdiv_pipe_fp16", Float16, div,
              opcode=opcode)

    def test_pipe_div_fp32(self):
        dut = FPDIVMuxInOut(32, 4)
        # don't forget to initialize opcode; don't use magic numbers
        opcode = int(DivPipeCoreOperation.UDivRem)
        runfp(dut, 32, "test_fpdiv_pipe_fp32", Float32, div,
              opcode=opcode)

    def test_pipe_div_fp64(self):
        dut = FPDIVMuxInOut(64, 4)
        # don't forget to initialize opcode; don't use magic numbers
        opcode = int(DivPipeCoreOperation.UDivRem)
        runfp(dut, 64, "test_fpdiv_pipe_fp64", Float64, div,
              opcode=opcode)


if __name__ == '__main__':
    unittest.main()
