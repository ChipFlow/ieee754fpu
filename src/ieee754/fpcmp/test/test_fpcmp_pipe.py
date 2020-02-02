""" test of FPCVTMuxInOut
"""

from ieee754.fpcmp.pipeline import (FPCMPMuxInOut)
from ieee754.fpcommon.test.fpmux import runfp

from sfpy import Float16, Float32, Float64
import math


def fpcmp_eq(a, b):
    return Float32(a.eq(b))

def fpcmp_lt(a, b):
    return Float32(a.lt(b))


def test_fpcmp_eq():
    dut = FPCMPMuxInOut(32, 4)
    runfp(dut, 32, "test_fpcmp_eq", Float32, fpcmp_eq,
          n_vals=100, opcode=0b10)

def test_fpcmp_lt():
    dut = FPCMPMuxInOut(32, 4)
    runfp(dut, 32, "test_fpcmp_lt", Float32, fpcmp_lt,
          n_vals=100, opcode=0b00)


if __name__ == '__main__':
    for i in range(50):
        test_fpcmp_lt()
        test_fpcmp_eq()
