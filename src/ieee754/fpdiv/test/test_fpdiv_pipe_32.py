""" test of FPDIVMuxInOut
"""

from ieee754.fpdiv.pipeline import (FPDIVMuxInOut,)
from ieee754.fpcommon.test.case_gen import run_pipe_fp
from ieee754.fpcommon.test import unit_test_single
from ieee754.fpdiv.test.div_data32 import regressions
from ieee754.div_rem_sqrt_rsqrt.core import DivPipeCoreOperation

import unittest
from sfpy import Float32
from operator import truediv as div


class TestDivPipe(unittest.TestCase):
    def test_pipe_fp32(self):
        dut = FPDIVMuxInOut(32, 4)
        # don't forget to initialize opcode; don't use magic numbers
        opcode = int(DivPipeCoreOperation.UDivRem)
        run_pipe_fp(dut, 32, "div32", unit_test_single, Float32,
                    regressions, div, 10, opcode=opcode)


if __name__ == '__main__':
    unittest.main()
