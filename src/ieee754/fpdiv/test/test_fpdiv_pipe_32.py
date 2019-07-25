""" test of FPDIVMuxInOut
"""

from ieee754.fpdiv.pipeline import (FPDIVMuxInOut,)
from ieee754.fpcommon.test.case_gen import run_pipe_fp
from ieee754.fpcommon.test import unit_test_single
from ieee754.fpdiv.test.div_data32 import regressions

import unittest
from sfpy import Float32
from operator import truediv as div


class TestDivPipe(unittest.TestCase):
    def test_pipe_fp32(self):
        dut = FPDIVMuxInOut(32, 4)
        run_pipe_fp(dut, 32, "div32", unit_test_single, Float32,
                    regressions, div, 10)


if __name__ == '__main__':
    unittest.main()
