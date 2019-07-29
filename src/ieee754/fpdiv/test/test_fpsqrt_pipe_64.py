""" test of FPDIVMuxInOut
"""

from ieee754.fpdiv.pipeline import (FPDIVMuxInOut,)
from ieee754.fpcommon.test.case_gen import run_pipe_fp
from ieee754.fpcommon.test import unit_test_double
#from ieee754.fpdiv.test.sqrt_data64 import regressions
from ieee754.div_rem_sqrt_rsqrt.core import DivPipeCoreOperation

import unittest
from sfpy import Float64


def sqrt(x):
    return x.sqrt()


class TestDivPipe(unittest.TestCase):
    def test_pipe_sqrt_fp64(self):
        dut = FPDIVMuxInOut(64, 4)
        # don't forget to initialize opcode; don't use magic numbers
        opcode = int(DivPipeCoreOperation.SqrtRem)
        run_pipe_fp(dut, 64, "sqrt64", unit_test_double, Float64, None,
                    sqrt, 100, single_op=True, opcode=opcode)

if __name__ == '__main__':
    unittest.main()
