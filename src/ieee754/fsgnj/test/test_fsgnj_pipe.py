""" test of FPCVTMuxInOut
"""

from ieee754.fsgnj.pipeline import (FSGNJMuxInOut)
from ieee754.fpcommon.test.fpmux import runfp

import sfpy
from sfpy import Float64, Float32, Float16



######################
# signed int to fp
######################

def fsgnj_f32_mov(a, b):
    return Float32.from_bits((a.bits & 0x7fffffff) | (b.bits & 0x80000000))

def fsgnj_f32_neg(a, b):
    sign = b.bits & 0x80000000
    sign = sign ^ 0x80000000
    return Float32.from_bits((a.bits & 0x7fffffff) | sign)

def fsgnj_f32_abs(a, b):
    bsign = b.bits & 0x80000000
    asign = a.bits & 0x80000000
    sign = asign ^ bsign
    return Float32.from_bits((a.bits & 0x7fffffff) | sign)

def test_fsgnj_mov():
    dut = FSGNJMuxInOut(32, 4)
    runfp(dut, 32, "test_fsgnj_f32_mov", Float32, fsgnj_f32_mov,
                False, n_vals=10, opcode=0x0)
def test_fsgnj_neg():
    dut = FSGNJMuxInOut(32, 4)
    runfp(dut, 32, "test_fsgnj_f32_neg", Float32, fsgnj_f32_neg,
                False, n_vals=10, opcode=0x1)

def test_fsgnj_abs():
    dut = FSGNJMuxInOut(32, 4)
    runfp(dut, 32, "test_fsgnj_f32_abs", Float32, fsgnj_f32_abs,
                False, n_vals=10, opcode=0x2)


if __name__ == '__main__':
    for i in range(50):
        test_fsgnj_mov()
        test_fsgnj_neg()
        test_fsgnj_abs()
