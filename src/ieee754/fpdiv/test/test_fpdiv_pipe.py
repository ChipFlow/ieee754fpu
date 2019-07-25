""" test of FPDIVMuxInOut
"""

from ieee754.fpdiv.pipeline import (FPDIVMuxInOut,)
from ieee754.fpcommon.test.fpmux import runfp

import unittest
from sfpy import Float64, Float32, Float16
from operator import truediv as div


class TestDivPipe(unittest.TestCase):
    def test_pipe_div_fp16(self):
        dut = FPDIVMuxInOut(16, 4)
        runfp(dut, 16, "test_fpdiv_pipe_fp16", Float16, div)

    def test_pipe_div_fp32(self):
        dut = FPDIVMuxInOut(32, 4)
        runfp(dut, 32, "test_fpdiv_pipe_fp32", Float32, div)

    def test_pipe_div_fp64(self):
        dut = FPDIVMuxInOut(64, 4)
        runfp(dut, 64, "test_fpdiv_pipe_fp64", Float64, div)


if __name__ == '__main__':
    unittest.main()
