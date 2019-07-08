from random import randint
from random import seed

import sys
from sfpy import Float32

def get_mantissa(x):
    return 0x7fffff & x

def get_exponent(x):
    return ((x & 0x7f800000) >> 23) - 127

def set_exponent(x, e):
    return (x & ~0x7f800000) | ((e+127) << 23)

def get_sign(x):
    return ((x & 0x80000000) >> 31)

def is_nan(x):
    return get_exponent(x) == 128 and get_mantissa(x) != 0

def is_inf(x):
    return get_exponent(x) == 128 and get_mantissa(x) == 0

def is_pos_inf(x):
    return is_inf(x) and not get_sign(x)

def is_neg_inf(x):
    return is_inf(x) and get_sign(x)

def match(x, y):
    return (
        (is_pos_inf(x) and is_pos_inf(y)) or
        (is_neg_inf(x) and is_neg_inf(y)) or
        (is_nan(x) and is_nan(y)) or
        (x == y)
        )

def create(s, e, x):
    return (s<<31) | ((e+127) << 23) | m

def inf(s):
    return create(s, 128, 0)

def nan(s):
    return create(s, 128, 1<<23)

def zero(s):
    return s<<31


def get_rs_case(dut, a, b, mid):
    in_a, in_b = dut.rs[0]
    out_z = dut.res[0]
    yield dut.ids.in_mid.eq(mid)
    yield in_a.v.eq(a)
    yield in_a.valid_i.eq(1)
    yield
    yield
    yield
    yield
    a_ack = (yield in_a.ready_o)
    assert a_ack == 0

    yield in_a.valid_i.eq(0)

    yield in_b.v.eq(b)
    yield in_b.valid_i.eq(1)
    yield
    yield
    b_ack = (yield in_b.ready_o)
    assert b_ack == 0

    yield in_b.valid_i.eq(0)

    yield out_z.ready_i.eq(1)

    while True:
        out_z_stb = (yield out_z.valid_o)
        if not out_z_stb:
            yield
            continue
        vout_z = yield out_z.v
        #out_mid = yield dut.ids.out_mid
        yield out_z.ready_i.eq(0)
        yield
        break

    return vout_z, mid

def check_rs_case(dut, a, b, z, mid=None):
    if mid is None:
        mid = randint(0, 6)
    mid = 0
    out_z, out_mid = yield from get_rs_case(dut, a, b, mid)
    assert out_z == z, "Output z 0x%x not equal to expected 0x%x" % (out_z, z)
    assert out_mid == mid, "Output mid 0x%x != expected 0x%x" % (out_mid, mid)


def get_case(dut, a, b, mid):
    #yield dut.in_mid.eq(mid)
    yield dut.in_a.v.eq(a)
    yield dut.in_a.valid_i_test.eq(1)
    yield
    yield
    yield
    yield
    a_ack = (yield dut.in_a.ready_o)
    assert a_ack == 0

    yield dut.in_a.valid_i.eq(0)

    yield dut.in_b.v.eq(b)
    yield dut.in_b.valid_i.eq(1)
    yield
    yield
    b_ack = (yield dut.in_b.ready_o)
    assert b_ack == 0

    yield dut.in_b.valid_i.eq(0)

    yield dut.out_z.ready_i.eq(1)

    while True:
        out_z_stb = (yield dut.out_z.valid_o)
        if not out_z_stb:
            yield
            continue
        out_z = yield dut.out_z.v
        #out_mid = yield dut.out_mid
        yield dut.out_z.ready_i.eq(0)
        yield
        break

    return out_z, mid # TODO: mid

def check_case(dut, a, b, z, mid=None):
    if mid is None:
        mid = randint(0, 6)
    mid = 0
    out_z, out_mid = yield from get_case(dut, a, b, mid)
    assert out_z == z, "Output z 0x%x not equal to expected 0x%x" % (out_z, z)
    assert out_mid == mid, "Output mid 0x%x != expected 0x%x" % (out_mid, mid)


def run_fpunit(dut, stimulus_a, stimulus_b, op, get_case_fn):

    expected_responses = []
    actual_responses = []
    for a, b in zip(stimulus_a, stimulus_b):
        mid = randint(0, 6)
        mid = 0
        af = Float32.from_bits(a)
        bf = Float32.from_bits(b)
        z = op(af, bf)
        expected_responses.append((z.get_bits(), mid))
        actual = yield from get_case_fn(dut, a, b, mid)
        actual_responses.append(actual)

    if len(actual_responses) < len(expected_responses):
        print ("Fail ... not enough results")
        exit(0)

    for expected, actual, a, b in zip(expected_responses, actual_responses,
                                      stimulus_a, stimulus_b):
        passed = match(expected[0], actual[0])
        if expected[1] != actual[1]: # check mid
            print ("MID failed", expected[1], actual[1])
            sys.exit(0)

        if not passed:

            expected = expected[0]
            actual = actual[0]
            print ("Fail ... expected:", hex(expected), "actual:", hex(actual))

            print (hex(a))
            print ("a mantissa:", a & 0x7fffff)
            print ("a exponent:", ((a & 0x7f800000) >> 23) - 127)
            print ("a sign:", ((a & 0x80000000) >> 31))

            print (hex(b))
            print ("b mantissa:", b & 0x7fffff)
            print ("b exponent:", ((b & 0x7f800000) >> 23) - 127)
            print ("b sign:", ((b & 0x80000000) >> 31))

            print (hex(expected))
            print ("expected mantissa:", expected & 0x7fffff)
            print ("expected exponent:", ((expected & 0x7f800000) >> 23) - 127)
            print ("expected sign:", ((expected & 0x80000000) >> 31))

            print (hex(actual))
            print ("actual mantissa:", actual & 0x7fffff)
            print ("actual exponent:", ((actual & 0x7f800000) >> 23) - 127)
            print ("actual sign:", ((actual & 0x80000000) >> 31))

            sys.exit(0)

corner_cases = [0x80000000, 0x00000000, 0x7f800000, 0xff800000,
                0x7fc00000, 0xffc00000]

def run_corner_cases(dut, count, op, get_case_fn):
    #corner cases
    from itertools import permutations
    stimulus_a = [i[0] for i in permutations(corner_cases, 2)]
    stimulus_b = [i[1] for i in permutations(corner_cases, 2)]
    yield from run_fpunit(dut, stimulus_a, stimulus_b, op, get_case_fn)
    count += len(stimulus_a)
    print (count, "vectors passed")

def run_fpunit_2(dut, stimulus_a, stimulus_b, op, get_case_fn):
    yield from run_fpunit(dut, stimulus_a, stimulus_b, op, get_case_fn)
    yield from run_fpunit(dut, stimulus_b, stimulus_a, op, get_case_fn)

def run_cases(dut, count, op, fixed_num, maxcount, get_case_fn):
    if isinstance(fixed_num, int):
        stimulus_a = [fixed_num for i in range(maxcount)]
        report = hex(fixed_num)
    else:
        stimulus_a = fixed_num
        report = "random"

    stimulus_b = [randint(0, 1<<32) for i in range(maxcount)]
    yield from run_fpunit_2(dut, stimulus_a, stimulus_b, op, get_case_fn)
    count += len(stimulus_a)
    print (count, "vectors passed 2^32", report)

    # non-canonical NaNs.
    stimulus_b = [set_exponent(randint(0, 1<<32), 128) \
                        for i in range(maxcount)]
    yield from run_fpunit_2(dut, stimulus_a, stimulus_b, op, get_case_fn)
    count += len(stimulus_a)
    print (count, "vectors passed Non-Canonical NaN", report)

    # -127
    stimulus_b = [set_exponent(randint(0, 1<<32), -127) \
                        for i in range(maxcount)]
    yield from run_fpunit_2(dut, stimulus_a, stimulus_b, op, get_case_fn)
    count += len(stimulus_a)
    print (count, "vectors passed exp=-127", report)

    # nearly zero
    stimulus_b = [set_exponent(randint(0, 1<<32), -126) \
                        for i in range(maxcount)]
    yield from run_fpunit_2(dut, stimulus_a, stimulus_b, op, get_case_fn)
    count += len(stimulus_a)
    print (count, "vectors passed exp=-126", report)

    # nearly inf
    stimulus_b = [set_exponent(randint(0, 1<<32), 127) \
                        for i in range(maxcount)]
    yield from run_fpunit_2(dut, stimulus_a, stimulus_b, op, get_case_fn)
    count += len(stimulus_a)
    print (count, "vectors passed exp=127", report)

    return count

def run_edge_cases(dut, count, op, get_case_fn, maxcount=10, num_loops=1000):
    #edge cases
    for testme in corner_cases:
        count = yield from run_cases(dut, count, op, testme,
                                     maxcount, get_case_fn)

    for i in range(num_loops):
        stimulus_a = [randint(0, 1<<32) for i in range(maxcount)]
        count = yield from run_cases(dut, count, op, stimulus_a, 10,
                                     get_case_fn)
    return count

