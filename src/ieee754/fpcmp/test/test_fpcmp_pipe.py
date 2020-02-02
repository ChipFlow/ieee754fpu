""" test of FPCVTMuxInOut
"""

from ieee754.fpcmp.pipeline import (FPCMPMuxInOut)
from ieee754.fpcommon.test.fpmux import runfp
from ieee754.fpcommon.test.case_gen import run_pipe_fp
from ieee754.fpcommon.test import unit_test_single

from sfpy import Float16, Float32, Float64
import math


def fpcmp_eq(a, b):
    return Float32(a.eq(b))

def fpcmp_lt(a, b):
    return Float32(a.lt(b))

def fpcmp_le(a, b):
    return Float32(a.le(b))

def test_fpcmp_eq():
    dut = FPCMPMuxInOut(32, 4)
    runfp(dut, 32, "test_fpcmp_eq", Float32, fpcmp_eq,
          n_vals=100, opcode=0b10)

def test_fpcmp_lt():
    dut = FPCMPMuxInOut(32, 4)
    runfp(dut, 32, "test_fpcmp_lt", Float32, fpcmp_lt,
          n_vals=100, opcode=0b00)

def test_fpcmp_le():
    dut = FPCMPMuxInOut(32, 4)
    runfp(dut, 32, "test_fpcmp_le", Float32, fpcmp_le,
          n_vals=100, opcode=0b01)

def cornercases():
    nan = Float32(float('nan')).bits
    yield nan, Float32(1.0).bits
    yield Float32(1.0).bits, nan
    yield nan, nan
    yield Float32(0.0).bits, Float32(-0.0).bits
    yield Float32(-0.0).bits, Float32(0.0).bits

def test_fpcmp_cornercases():
    dut = FPCMPMuxInOut(32, 4)
    run_pipe_fp(dut, 32, "test_fpcmp_f32_corner_eq", unit_test_single,
                Float32, cornercases, fpcmp_eq, 5,
                opcode=0b10)
    run_pipe_fp(dut, 32, "test_fpcmp_f32_corner_le", unit_test_single,
                Float32, cornercases, fpcmp_le, 5,
                opcode=0b01)
    run_pipe_fp(dut, 32, "test_fpcmp_f32_corner_lt", unit_test_single,
                Float32, cornercases, fpcmp_lt, 5,
                opcode=0b00)


if __name__ == '__main__':
    test_fpcmp_cornercases()
    # for i in range(50):
    #     test_fpcmp_lt()
    #     test_fpcmp_eq()
    #     test_fpcmp_le()
