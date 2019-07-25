""" test of FPDIVMuxInOut
"""

from ieee754.fpdiv.pipeline import (FPDIVMuxInOut,)
from ieee754.fpcommon.test.case_gen import run_pipe_fp
from ieee754.fpcommon.test import unit_test_half
from ieee754.fpdiv.test.div_data16 import regressions

import unittest
from sfpy import Float16
from operator import truediv as div


class TestDivPipe(unittest.TestCase):
    def test_pipe_fp16(self):
        dut = FPDIVMuxInOut(16, 4)
        run_pipe_fp(dut, 16, "div16", unit_test_half, Float16,
                    regressions, div, 10)


if __name__ == '__main__':
    unittest.main()
