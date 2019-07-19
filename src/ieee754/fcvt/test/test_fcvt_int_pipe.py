""" test of FPCVTMuxInOut
"""

from ieee754.fcvt.pipeline import (FPCVTIntMuxInOut,)
from ieee754.fpcommon.test.fpmux import runfp

import sfpy
from sfpy import Float64, Float32, Float16

def to_int16(x):
    """ input: an unsigned int in the range 0..65535
        output: a signed int in the range -32768..32767
    """
    if x > 32767:
        return x-0x10000
    return x

def to_int32(x):
    """ input: an unsigned int in the range 0..2^32-1
        output: a signed int in the range -2^31..2^31-1
    """
    if x > ((1<<31)-1):
        return x-(1<<32)
    return x

def to_uint16(x):
    return x

def to_uint32(x):
    return x

def to_uint64(x):
    return x

def fcvt_64(x):
    return sfpy.float.ui32_to_f64(x)

def fcvt_i16_f32(x):
    print ("fcvt i16_f32", hex(x))
    return sfpy.float.i32_to_f32(x) # XXX no i16_to_f32, it's ok though

def fcvt_i32_f32(x):
    print ("fcvt i32_f32", hex(x))
    return sfpy.float.i32_to_f32(x)

def fcvt_i32_f64(x):
    print ("fcvt i32_f64", hex(x))
    return sfpy.float.i32_to_f64(x)

def fcvt_32(x):
    return sfpy.float.ui32_to_f32(x)

def fcvt_64_to_32(x):
    return sfpy.float.ui64_to_f32(x)

def fcvt_16(x):
    return sfpy.float.ui32_to_f16(x)

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

######################
# unsigned int to fp
######################

def test_int_pipe_ui16_f32():
    # XXX softfloat-3 doesn't have ui16_to_xxx so use ui32 instead.
    # should be fine.
    dut = FPCVTIntMuxInOut(16, 32, 4, op_wid=1)
    runfp(dut, 16, "test_fcvt_int_pipe_ui16_f32", to_uint16, fcvt_32, True,
          n_vals=100)

def test_int_pipe_ui16_f64():
    dut = FPCVTIntMuxInOut(16, 64, 4, op_wid=1)
    runfp(dut, 16, "test_fcvt_int_pipe_ui16_f64", to_uint16, fcvt_64, True,
          n_vals=100)

def test_int_pipe_ui32_f32():
    dut = FPCVTIntMuxInOut(32, 32, 4, op_wid=1)
    runfp(dut, 32, "test_fcvt_int_pipe_ui32_32", to_uint32, fcvt_32, True,
          n_vals=100)

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

if __name__ == '__main__':
    for i in range(200):
        test_int_pipe_ui32_f32()
        test_int_pipe_i32_f32()
        continue
        test_int_pipe_i16_f32()
        test_int_pipe_i32_f64()
        continue
        test_int_pipe_ui16_f32()
        test_int_pipe_ui64_f32()
        test_int_pipe_ui32_f16()
        test_int_pipe_ui64_f16()
        test_int_pipe_ui16_f64()
        test_int_pipe_ui32_f64()

