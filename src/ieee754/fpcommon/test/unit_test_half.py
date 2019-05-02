from random import randint
from random import seed

import sys
from sfpy import Float16

def get_mantissa(x):
    return 0x3ff & x

def get_exponent(x):
    return ((x & 0xf800) >> 11) - 15

def get_sign(x):
    return ((x & 0x8000) >> 15)

def is_nan(x):
    return get_exponent(x) == 16 and get_mantissa(x) != 0

def is_inf(x):
    return get_exponent(x) == 16 and get_mantissa(x) == 0

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

def get_case(dut, a, b):
    yield dut.in_a.v.eq(a)
    yield dut.in_a.stb.eq(1)
    yield
    yield
    a_ack = (yield dut.in_a.ack)
    assert a_ack == 0
    yield dut.in_b.v.eq(b)
    yield dut.in_b.stb.eq(1)
    b_ack = (yield dut.in_b.ack)
    assert b_ack == 0

    while True:
        yield
        out_z_stb = (yield dut.out_z.stb)
        if not out_z_stb:
            continue
        yield dut.in_a.stb.eq(0)
        yield dut.in_b.stb.eq(0)
        yield dut.out_z.ack.eq(1)
        yield
        yield dut.out_z.ack.eq(0)
        yield
        yield
        break

    out_z = yield dut.out_z.v
    return out_z

def check_case(dut, a, b, z):
    out_z = yield from get_case(dut, a, b)
    assert out_z == z, "Output z 0x%x not equal to expected 0x%x" % (out_z, z)


def run_test(dut, stimulus_a, stimulus_b, op):

    expected_responses = []
    actual_responses = []
    for a, b in zip(stimulus_a, stimulus_b):
        af = Float16.from_bits(a)
        bf = Float16.from_bits(b)
        z = op(af, bf)
        expected_responses.append(z.get_bits())
        #print (af, bf, z)
        actual = yield from get_case(dut, a, b)
        actual_responses.append(actual)

    if len(actual_responses) < len(expected_responses):
        print ("Fail ... not enough results")
        exit(0)

    for expected, actual, a, b in zip(expected_responses, actual_responses,
                                      stimulus_a, stimulus_b):
        passed = match(expected, actual)

        if not passed:

            print ("Fail ... expected:", hex(expected), "actual:", hex(actual))

            print (hex(a))
            print ("a mantissa:", get_mantissa(a))
            print ("a exponent:", get_exponent(a))
            print ("a sign:", get_sign(a))

            print (hex(b))
            print ("b mantissa:", get_mantissa(b))
            print ("b exponent:", get_exponent(b))
            print ("b sign:", get_sign(b))

            print (hex(expected))
            print ("expected mantissa:", get_mantissa(expected))
            print ("expected exponent:", get_exponent(expected))
            print ("expected sign:", get_sign(expected))

            print (hex(actual))
            print ("actual mantissa:", get_mantissa(actual))
            print ("actual exponent:", get_exponent(actual))
            print ("actual sign:", get_sign(actual))

            sys.exit(0)

def run_corner_cases(dut, count, op):
    #corner cases
    corners = [0x8000, 0x0000, 0x7800, 0xf800, 0x7c00, 0xfc00]
    from itertools import permutations
    stimulus_a = [i[0] for i in permutations(corners, 2)]
    stimulus_b = [i[1] for i in permutations(corners, 2)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")


def run_edge_cases(dut, count, op):
    maxint16 = 1<<16
    maxcount = 10
    #edge cases
    stimulus_a = [0x8000 for i in range(maxcount)]
    stimulus_b = [randint(0, maxint16-1) for i in range(maxcount)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_a = [0x0000 for i in range(maxcount)]
    stimulus_b = [randint(0, maxint16-1) for i in range(maxcount)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0x8000 for i in range(maxcount)]
    stimulus_a = [randint(0, maxint16-1) for i in range(maxcount)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0x0000 for i in range(maxcount)]
    stimulus_a = [randint(0, maxint16-1) for i in range(maxcount)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_a = [0x7800 for i in range(maxcount)]
    stimulus_b = [randint(0, maxint16-1) for i in range(maxcount)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_a = [0xF800 for i in range(maxcount)]
    stimulus_b = [randint(0, maxint16-1) for i in range(maxcount)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0x7800 for i in range(maxcount)]
    stimulus_a = [randint(0, maxint16-1) for i in range(maxcount)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0xF800 for i in range(maxcount)]
    stimulus_a = [randint(0, maxint16-1) for i in range(maxcount)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_a = [0x7C00 for i in range(maxcount)]
    stimulus_b = [randint(0, maxint16-1) for i in range(maxcount)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_a = [0xFC00 for i in range(maxcount)]
    stimulus_b = [randint(0, maxint16-1) for i in range(maxcount)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0x7C00 for i in range(maxcount)]
    stimulus_a = [randint(0, maxint16-1) for i in range(maxcount)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0xFC00 for i in range(maxcount)]
    stimulus_a = [randint(0, maxint16-1) for i in range(maxcount)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    #seed(0)
    for i in range(100000):
        stimulus_a = [randint(0, maxint16-1) for i in range(maxcount)]
        stimulus_b = [randint(0, maxint16-1) for i in range(maxcount)]
        yield from run_test(dut, stimulus_a, stimulus_b, op)
        count += maxcount
        print (count, "random vectors passed")

