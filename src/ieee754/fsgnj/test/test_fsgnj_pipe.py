""" test of FPCVTMuxInOut
"""

from ieee754.fsgnj.pipeline import (FSGNJMuxInOut)
from ieee754.fpcommon.test.fpmux import runfp

from sfpy import Float16, Float32, Float64


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


def fsgnj_f16_mov(a, b):
    return Float16.from_bits((a.bits & 0x7fff) | (b.bits & 0x8000))


def fsgnj_f16_neg(a, b):
    sign = b.bits & 0x8000
    sign = sign ^ 0x8000
    return Float16.from_bits((a.bits & 0x7fff) | sign)


def fsgnj_f16_abs(a, b):
    bsign = b.bits & 0x8000
    asign = a.bits & 0x8000
    sign = asign ^ bsign
    return Float16.from_bits((a.bits & 0x7fff) | sign)


def fsgnj_f64_mov(a, b):
    return Float64.from_bits((a.bits & 0x7fffffffffffffff) |
                             (b.bits & 0x8000000000000000))


def fsgnj_f64_neg(a, b):
    sign = b.bits & 0x8000000000000000
    sign = sign ^ 0x8000000000000000
    return Float64.from_bits((a.bits & 0x7fffffffffffffff) | sign)


def fsgnj_f64_abs(a, b):
    bsign = b.bits & 0x8000000000000000
    asign = a.bits & 0x8000000000000000
    sign = asign ^ bsign
    return Float64.from_bits((a.bits & 0x7fffffffffffffff) | sign)


def test_fsgnj_f32_mov():
    dut = FSGNJMuxInOut(32, 4)
    runfp(dut, 32, "test_fsgnj_f32_mov", Float32, fsgnj_f32_mov,
          n_vals=100, opcode=0x0)


def test_fsgnj_f32_neg():
    dut = FSGNJMuxInOut(32, 4)
    runfp(dut, 32, "test_fsgnj_f32_neg", Float32, fsgnj_f32_neg,
          n_vals=100, opcode=0x1)


def test_fsgnj_f32_abs():
    dut = FSGNJMuxInOut(32, 4)
    runfp(dut, 32, "test_fsgnj_f32_abs", Float32, fsgnj_f32_abs,
          n_vals=100, opcode=0x2)


def test_fsgnj_f16_mov():
    dut = FSGNJMuxInOut(16, 4)
    runfp(dut, 16, "test_fsgnj_f16_mov", Float16, fsgnj_f16_mov,
          n_vals=100, opcode=0x0)


def test_fsgnj_f16_neg():
    dut = FSGNJMuxInOut(16, 4)
    runfp(dut, 16, "test_fsgnj_f16_neg", Float16, fsgnj_f16_neg,
          n_vals=100, opcode=0x1)


def test_fsgnj_f16_abs():
    dut = FSGNJMuxInOut(16, 4)
    runfp(dut, 16, "test_fsgnj_f16_abs", Float16, fsgnj_f16_abs,
          n_vals=100, opcode=0x2)


def test_fsgnj_f64_mov():
    dut = FSGNJMuxInOut(64, 4)
    runfp(dut, 64, "test_fsgnj_f64_mov", Float64, fsgnj_f64_mov,
          n_vals=100, opcode=0x0)


def test_fsgnj_f64_neg():
    dut = FSGNJMuxInOut(64, 4)
    runfp(dut, 64, "test_fsgnj_f64_neg", Float64, fsgnj_f64_neg,
          n_vals=100, opcode=0x1)


def test_fsgnj_f64_abs():
    dut = FSGNJMuxInOut(64, 4)
    runfp(dut, 64, "test_fsgnj_f64_abs", Float64, fsgnj_f64_abs,
          n_vals=100, opcode=0x2)


if __name__ == '__main__':
    for i in range(50):
        test_fsgnj_f32_mov()
        test_fsgnj_f32_neg()
        test_fsgnj_f32_abs()
        test_fsgnj_f16_mov()
        test_fsgnj_f16_neg()
        test_fsgnj_f16_abs()
        test_fsgnj_f64_mov()
        test_fsgnj_f64_neg()
        test_fsgnj_f64_abs()
