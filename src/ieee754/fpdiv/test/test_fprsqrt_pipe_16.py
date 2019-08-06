""" test of FPDIVMuxInOut
"""

from ieee754.fpdiv.pipeline import (FPDIVMuxInOut,)
from ieee754.fpcommon.test.case_gen import run_pipe_fp
from ieee754.fpcommon.test import unit_test_half
#from ieee754.fpdiv.test.rsqrt_data16 import regressions
from ieee754.div_rem_sqrt_rsqrt.core import DivPipeCoreOperation

import unittest
from sfpy import Float16, Float64


def rsqrt(x):
    # FIXME: switch to correct implementation
    # needs to use exact arithmetic and rounding only once at the end
    return x.__class__(float(Float64(1.0) / x.to_f64().sqrt()))


class TestDivPipe(unittest.TestCase):
    def test_pipe_rsqrt_fp16(self):
        dut = FPDIVMuxInOut(16, 8)
        # don't forget to initialize opcode; don't use magic numbers
        opcode = int(DivPipeCoreOperation.RSqrtRem)
        run_pipe_fp(dut, 16, "rsqrt16", unit_test_half, Float16, None,
                    rsqrt, 100, single_op=True, opcode=opcode)

if __name__ == '__main__':
    unittest.main()
