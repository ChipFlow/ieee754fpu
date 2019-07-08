""" test of FPDIVMuxInOut
"""

from ieee754.fpdiv.pipeline import (FPDIVMuxInOut,)
from ieee754.fpcommon.test.case_gen import run_pipe_fp
from ieee754.fpcommon.test import unit_test_single
from ieee754.fpdiv.test.div_data32 import regressions

from sfpy import Float32
from operator import truediv as div

def test_pipe_fp32():
    dut = FPDIVMuxInOut(32, 4)
    run_pipe_fp(dut, 32, "div", unit_test_single, Float32,
                   regressions, div, 10)

if __name__ == '__main__':
    test_pipe_fp32()
