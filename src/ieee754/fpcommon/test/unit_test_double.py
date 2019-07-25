import sys
from random import randint
from random import seed

from sfpy import Float64

max_e = 1024

def get_mantissa(x):
    return x & 0x000fffffffffffff

def get_exponent(x):
    return ((x & 0x7ff0000000000000) >> 52) - 1023

def set_exponent(x, e):
    return (x & ~0x7ff0000000000000) | ((e+1023) << 52)

def get_sign(x):
    return ((x & 0x8000000000000000) >> 63)

def is_nan(x):
    return get_exponent(x) == 1024 and get_mantissa(x) != 0

def is_inf(x):
    return get_exponent(x) == 1024 and get_mantissa(x) == 0

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

def create(s, e, m):
    return set_exponent((s<<63) | m, e)

def inf(s):
    return create(s, 1024, 0)

def nan(s):
    return create(s, 1024, 1<<51)

def zero(s):
    return s<<63

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
        af = Float64.from_bits(a)
        bf = Float64.from_bits(b)
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

            print ("Fail ... expected:", hex(exp), "actual:", hex(act))

            print (hex(a))
            print ("a mantissa:",              a & 0x000fffffffffffff)
            print ("a exponent:",            ((a & 0x7ff0000000000000) >> 52)\
                                                - 1023)
            print ("a sign:",                ((a & 0x8000000000000000) >> 63))

            print (hex(b))
            print ("b mantissa:",              b & 0x000fffffffffffff)
            print ("b exponent:",            ((b & 0x7ff0000000000000) >> 52)\
                                                 - 1023)
            print ("b sign:",                ((b & 0x8000000000000000) >> 63))

            print (hex(exp))
            print ("expected mantissa:",   exp & 0x000fffffffffffff)
            print ("expected exponent:", ((exp & 0x7ff0000000000000) >> 52)\
                                                 - 1023)
            print ("expected sign:",     ((exp & 0x8000000000000000) >> 63))

            print (hex(act))
            print ("actual mantissa:",       act & 0x000fffffffffffff)
            print ("actual exponent:",     ((act & 0x7ff0000000000000) >> 52)\
                                                 - 1023)
            print ("actual sign:",         ((act & 0x8000000000000000) >> 63))

            sys.exit(0)


def run_corner_cases(dut, count, op, get_case_fn):
    #corner cases
    from itertools import permutations
    stimulus_a = [i[0] for i in permutations([
        0x8000000000000000,
        0x0000000000000000,
        0x7ff8000000000000,
        0xfff8000000000000,
        0x7ff0000000000000,
        0xfff0000000000000
    ], 2)]
    stimulus_b = [i[1] for i in permutations([
        0x8000000000000000,
        0x0000000000000000,
        0x7ff8000000000000,
        0xfff8000000000000,
        0x7ff0000000000000,
        0xfff0000000000000
    ], 2)]
    yield from run_fpunit(dut, stimulus_a, stimulus_b, op, get_case_fn)
    count += len(stimulus_a)
    print (count, "vectors passed")


def run_edge_cases(dut, count, op, get_case_fn, maxcount=1000, num_loops=1000):
    #edge cases
    stimulus_a = [0x8000000000000000 for i in range(maxcount)]
    stimulus_b = [randint(0, 1<<64)  for i in range(maxcount)]
    yield from run_fpunit(dut, stimulus_a, stimulus_b, op, get_case_fn)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_a = [0x0000000000000000 for i in range(maxcount)]
    stimulus_b = [randint(0, 1<<64)  for i in range(maxcount)]
    yield from run_fpunit(dut, stimulus_a, stimulus_b, op, get_case_fn)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0x8000000000000000 for i in range(maxcount)]
    stimulus_a = [randint(0, 1<<64)  for i in range(maxcount)]
    yield from run_fpunit(dut, stimulus_a, stimulus_b, op, get_case_fn)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0x0000000000000000 for i in range(maxcount)]
    stimulus_a = [randint(0, 1<<64)  for i in range(maxcount)]
    yield from run_fpunit(dut, stimulus_a, stimulus_b, op, get_case_fn)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_a = [0x7FF8000000000000 for i in range(maxcount)]
    stimulus_b = [randint(0, 1<<64)  for i in range(maxcount)]
    yield from run_fpunit(dut, stimulus_a, stimulus_b, op, get_case_fn)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_a = [0xFFF8000000000000 for i in range(maxcount)]
    stimulus_b = [randint(0, 1<<64)  for i in range(maxcount)]
    yield from run_fpunit(dut, stimulus_a, stimulus_b, op, get_case_fn)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0x7FF8000000000000 for i in range(maxcount)]
    stimulus_a = [randint(0, 1<<64) for i in range(maxcount)]
    yield from run_fpunit(dut, stimulus_a, stimulus_b, op, get_case_fn)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0xFFF8000000000000 for i in range(maxcount)]
    stimulus_a = [randint(0, 1<<64) for i in range(maxcount)]
    yield from run_fpunit(dut, stimulus_a, stimulus_b, op, get_case_fn)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_a = [0x7FF0000000000000 for i in range(maxcount)]
    stimulus_b = [randint(0, 1<<64)  for i in range(maxcount)]
    yield from run_fpunit(dut, stimulus_a, stimulus_b, op, get_case_fn)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_a = [0xFFF0000000000000 for i in range(maxcount)]
    stimulus_b = [randint(0, 1<<64)  for i in range(maxcount)]
    yield from run_fpunit(dut, stimulus_a, stimulus_b, op, get_case_fn)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0x7FF0000000000000 for i in range(maxcount)]
    stimulus_a = [randint(0, 1<<64)  for i in range(maxcount)]
    yield from run_fpunit(dut, stimulus_a, stimulus_b, op, get_case_fn)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0xFFF0000000000000 for i in range(maxcount)]
    stimulus_a = [randint(0, 1<<64)  for i in range(maxcount)]
    yield from run_fpunit(dut, stimulus_a, stimulus_b, op, get_case_fn)
    count += len(stimulus_a)
    print (count, "vectors passed")

    #seed(0)
    for i in range(num_loops):
        stimulus_a = [randint(0, 1<<64) for i in range(maxcount)]
        stimulus_b = [randint(0, 1<<64) for i in range(maxcount)]
        yield from run_fpunit(dut, stimulus_a, stimulus_b, op, get_case_fn)
        count += maxcount
        print (count, "random vectors passed")

