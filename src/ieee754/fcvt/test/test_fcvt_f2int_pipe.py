""" test of FPCVTMuxInOut
"""

from ieee754.fcvt.pipeline import (FPCVTF2IntMuxInOut,)
from ieee754.fpcommon.test.fpmux import (runfp, create_random)
from ieee754.fcvt.test.rangelimited import create_int

import sfpy
from sfpy import Float64, Float32, Float16

def fcvt_f64_ui32(x):
    return sfpy.float.f64_to_ui32(x)

def fcvt_f64_i32(x):
    return sfpy.float.f64_to_i32(x) & 0xffffffff

def fcvt_i16_f32(x):
    print ("fcvt i16_f32", hex(x))
    return sfpy.float.i32_to_f32(x) # XXX no i16_to_f32, it's ok though

def fcvt_i32_f32(x):
    print ("fcvt i32_f32", hex(x))
    return sfpy.float.i32_to_f32(x)

def fcvt_i32_f64(x):
    print ("fcvt i32_f64", hex(x))
    return sfpy.float.i32_to_f64(x)

def fcvt_f32_ui32(x):
    return sfpy.float.f32_to_ui32(x)

def fcvt_64_to_32(x):
    return sfpy.float.ui64_to_f32(x)

def fcvt_f64_ui64(x):
    return sfpy.float.f64_to_ui64(x)

def fcvt_f64_ui16(x):
    x = sfpy.float.f64_to_ui32(x)
    if x >= 0xffff:
        return 0xffff
    return x

def fcvt_f16_ui32(x):
    return sfpy.float.f16_to_ui32(x)

def fcvt_f16_ui16(x):
    return sfpy.float.f16_to_ui32(x) & 0xffff

def fcvt_f16_i16(x):
    x = sfpy.float.f16_to_i32(x)
    if x >= 0x7fff:
        return 0x7fff
    if x <= -0x8000:
        return 0x8000
    return x & 0xffff

def fcvt_f64_i16(x):
    x = sfpy.float.f64_to_i32(x)
    if x >= 0x7fff:
        return 0x7fff
    if x <= -0x8000:
        return 0x8000
    return x & 0xffff

def fcvt_f32_i32(x):
    return sfpy.float.f32_to_i32(x) & 0xffffffff

def fcvt_f64_i64(x):
    return sfpy.float.f64_to_i64(x) & 0xffffffffffffffff


######################
# signed int to fp
######################

def test_int_pipe_i16_f32():
    # XXX softfloat-3 doesn't have i16_to_xxx so use ui32 instead.
    # should be fine.
    dut = FPCVTIntMuxInOut(16, 32, 4, op_wid=1)
    runfp(dut, 16, "test_fcvt_int_pipe_i16_f32", to_int16, fcvt_i16_f32, True,
          n_vals=100, opcode=0x1)

def test_int_pipe_i32_f64():
    dut = FPCVTIntMuxInOut(32, 64, 4, op_wid=1)
    runfp(dut, 32, "test_fcvt_int_pipe_i32_f64", to_int32, fcvt_i32_f64, True,
          n_vals=100, opcode=0x1)

def test_int_pipe_i32_f32():
    dut = FPCVTIntMuxInOut(32, 32, 4, op_wid=1)
    runfp(dut, 32, "test_fcvt_int_pipe_i32_f32", to_int32, fcvt_i32_f32, True,
          n_vals=100, opcode=0x1)

def test_int_pipe_f64_i64():
    dut = FPCVTF2IntMuxInOut(64, 64, 4, op_wid=1)
    vals = []
    for i in range(100):
        vals.append(create_int(Float64, 64))
    vals += create_random(dut.num_rows, 64, True, 10)
    runfp(dut, 64, "test_fcvt_f2int_pipe_f64_i64", Float64, fcvt_f64_i64,
                True, vals=vals, opcode=0x1)

def test_int_pipe_f64_i32():
    # XXX TODO: reduce range of FP num to actually fit (almost) into I32
    # http://bugs.libre-riscv.org/show_bug.cgi?id=113
    dut = FPCVTF2IntMuxInOut(64, 32, 4, op_wid=1)
    vals = []
    for i in range(100):
        vals.append(create_int(Float64, 32))
    vals += create_random(dut.num_rows, 32, True, 10)
    runfp(dut, 64, "test_fcvt_f2int_pipe_f64_i32", Float64, fcvt_f64_i32,
                    True, vals=vals, opcode=0x1)

def test_int_pipe_f64_i16():
    # XXX TODO: reduce range of FP num to actually fit (almost) into I16
    # http://bugs.libre-riscv.org/show_bug.cgi?id=113
    dut = FPCVTF2IntMuxInOut(64, 16, 4, op_wid=1)
    vals = []
    for i in range(100):
        vals.append(create_int(Float64, 16))
    vals += create_random(dut.num_rows, 16, True, 10)
    runfp(dut, 64, "test_fcvt_f2int_pipe_f64_i16", Float64, fcvt_f64_i16,
                    True, vals=vals, opcode=0x1)

def test_int_pipe_f32_i32():
    dut = FPCVTF2IntMuxInOut(32, 32, 4, op_wid=1)
    runfp(dut, 32, "test_fcvt_f2int_pipe_f32_i32", Float32, fcvt_f32_i32,
                True, n_vals=100, opcode=0x1)

def test_int_pipe_f16_i16():
    dut = FPCVTF2IntMuxInOut(16, 16, 4, op_wid=1)
    runfp(dut, 16, "test_fcvt_f2int_pipe_f16_i16", Float16, fcvt_f16_i16,
                True, n_vals=100, opcode=0x1)

######################
# fp to unsigned int 
######################

def test_int_pipe_f16_ui16():
    # XXX softfloat-3 doesn't have ui16_to_xxx so use ui32 instead.
    # should be fine.
    dut = FPCVTF2IntMuxInOut(16, 16, 4, op_wid=1)
    runfp(dut, 16, "test_fcvt_f2int_pipe_f16_ui16", Float16, fcvt_f16_ui16,
                True, n_vals=100)

def test_int_pipe_ui16_f64():
    dut = FPCVTIntMuxInOut(16, 64, 4, op_wid=1)
    runfp(dut, 16, "test_fcvt_int_pipe_ui16_f64", to_uint16, fcvt_64, True,
          n_vals=100)

def test_int_pipe_f32_ui32():
    dut = FPCVTF2IntMuxInOut(32, 32, 4, op_wid=1)
    vals = []
    for i in range(100):
        vals.append(create_int(Float32, 32))
    vals += create_random(dut.num_rows, 32, True, 10)
    runfp(dut, 32, "test_fcvt_f2int_pipe_f32_ui32", Float32, fcvt_f32_ui32,
                    True, vals=vals)

def test_int_pipe_ui32_f64():
    dut = FPCVTIntMuxInOut(32, 64, 4, op_wid=1)
    runfp(dut, 32, "test_fcvt_int_pipe_ui32_64", to_uint32, fcvt_64, True,
          n_vals=100)

def test_int_pipe_ui64_f32():
    # ok, doing 33 bits here because it's pretty pointless (not entirely)
    # to do random numbers statistically likely 99.999% of the time to be
    # converted to Inf
    dut = FPCVTIntMuxInOut(64, 32, 4, op_wid=1)
    runfp(dut, 33, "test_fcvt_int_pipe_ui64_32", to_uint64, fcvt_64_to_32, True,
          n_vals=100)

def test_int_pipe_ui64_f16():
    # ok, doing 17 bits here because it's pretty pointless (not entirely)
    # to do random numbers statistically likely 99.999% of the time to be
    # converted to Inf
    dut = FPCVTIntMuxInOut(64, 16, 4, op_wid=1)
    runfp(dut, 17, "test_fcvt_int_pipe_ui64_16", to_uint64, fcvt_16, True,
          n_vals=100)

def test_int_pipe_ui32_f16():
    # ok, doing 17 bits here because it's pretty pointless (not entirely)
    # to do random numbers statistically likely 99.999% of the time to be
    # converted to Inf
    dut = FPCVTIntMuxInOut(32, 16, 4, op_wid=1)
    runfp(dut, 17, "test_fcvt_int_pipe_ui32_16", to_uint32, fcvt_16, True,
          n_vals=100)

def test_int_pipe_f64_ui64():
    dut = FPCVTF2IntMuxInOut(64, 64, 4, op_wid=1)
    vals = []
    for i in range(100):
        vals.append(create_int(Float64, 64))
    vals += create_random(dut.num_rows, 64, True, 10)
    runfp(dut, 64, "test_fcvt_f2int_pipe_f64_ui64", Float64, fcvt_f64_ui64,
                    True, vals=vals)

def test_int_pipe_f64_ui32():
    dut = FPCVTF2IntMuxInOut(64, 32, 4, op_wid=1)
    vals = []
    for i in range(100):
        vals.append(create_int(Float64, 32))
    vals += create_random(dut.num_rows, 32, True, 10)
    runfp(dut, 64, "test_fcvt_f2int_pipe_f64_ui32", Float64, fcvt_f64_ui32,
                    True, vals=vals)

def test_int_pipe_f64_ui16():
    dut = FPCVTF2IntMuxInOut(64, 16, 4, op_wid=1)
    vals = []
    for i in range(100):
        vals.append(create_int(Float64, 16))
    vals += create_random(dut.num_rows, 16, True, 10)
    runfp(dut, 64, "test_fcvt_f2int_pipe_f64_ui16", Float64, fcvt_f64_ui16,
                    True, vals=vals)

if __name__ == '__main__':
    for i in range(200):
        test_int_pipe_f64_i16()
        test_int_pipe_f64_i32()
        test_int_pipe_f64_ui16()
        test_int_pipe_f64_ui32()
        test_int_pipe_f16_i16()
        test_int_pipe_f32_i32()
        test_int_pipe_f64_i64()
        test_int_pipe_f64_ui64()
        test_int_pipe_f32_ui32()
        test_int_pipe_f16_ui16()
