""" test of FPDIVMuxInOut
"""

from ieee754.fpdiv.pipeline import (FPDIVMuxInOut,)
from ieee754.fpcommon.test.case_gen import run_pipe_fp
from ieee754.fpcommon.test import unit_test_half
from ieee754.fpdiv.test.sqrt_data16 import regressions
from ieee754.div_rem_sqrt_rsqrt.core import DivPipeCoreOperation

import unittest
from sfpy import Float16


def sqrt(x):
    return x.sqrt()


class TestDivPipe(unittest.TestCase):
    def test_pipe_sqrt_fp16(self):
        dut = FPDIVMuxInOut(16, 4)
        # don't forget to initialize opcode; don't use magic numbers
        opcode = int(DivPipeCoreOperation.SqrtRem)
        run_pipe_fp(dut, 16, "sqrt16", unit_test_half, Float16, regressions,
                    sqrt, 100, single_op=True, opcode=opcode)

if __name__ == '__main__':
    unittest.main()
