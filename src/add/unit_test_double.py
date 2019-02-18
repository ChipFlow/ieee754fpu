import sys
from random import randint
from random import seed

from sfpy import Float64

def get_mantissa(x):
    return x & 0x000fffffffffffff

def get_exponent(x):
    return ((x & 0x7ff0000000000000) >> 52) - 1023

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
        af = Float64.from_bits(a)
        bf = Float64.from_bits(b)
        z = op(af, bf)
        expected_responses.append(z.get_bits())
        #print (af, bf, z)
        actual = yield from get_case(dut, a, b)
        actual_responses.append(actual)

    if len(actual_responses) < len(expected_responses):
        print ("Fail ... not enough results")
        exit(0)

    for exp, act, a, b in zip(expected_responses, actual_responses,
                                      stimulus_a, stimulus_b):
        passed = match(exp, act)

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


def run_corner_cases(dut, count, op):
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
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")


def run_edge_cases(dut, count, op):
    #edge cases
    stimulus_a = [0x8000000000000000 for i in range(1000)]
    stimulus_b = [randint(0, 1<<64)  for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_a = [0x0000000000000000 for i in range(1000)]
    stimulus_b = [randint(0, 1<<64)  for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0x8000000000000000 for i in range(1000)]
    stimulus_a = [randint(0, 1<<64)  for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0x0000000000000000 for i in range(1000)]
    stimulus_a = [randint(0, 1<<64)  for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_a = [0x7FF8000000000000 for i in range(1000)]
    stimulus_b = [randint(0, 1<<64)  for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_a = [0xFFF8000000000000 for i in range(1000)]
    stimulus_b = [randint(0, 1<<64)  for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0x7FF8000000000000 for i in range(1000)]
    stimulus_a = [randint(0, 1<<64) for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0xFFF8000000000000 for i in range(1000)]
    stimulus_a = [randint(0, 1<<64) for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_a = [0x7FF0000000000000 for i in range(1000)]
    stimulus_b = [randint(0, 1<<64)  for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_a = [0xFFF0000000000000 for i in range(1000)]
    stimulus_b = [randint(0, 1<<64)  for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0x7FF0000000000000 for i in range(1000)]
    stimulus_a = [randint(0, 1<<64)  for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0xFFF0000000000000 for i in range(1000)]
    stimulus_a = [randint(0, 1<<64)  for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    #seed(0)
    for i in range(100000):
        stimulus_a = [randint(0, 1<<64) for i in range(1000)]
        stimulus_b = [randint(0, 1<<64) for i in range(1000)]
        yield from run_test(dut, stimulus_a, stimulus_b, op)
        count += 1000
        print (count, "random vectors passed")

