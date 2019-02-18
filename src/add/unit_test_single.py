from random import randint
from random import seed

import sys
from sfpy import Float32

def get_mantissa(x):
    return 0x7fffff & x

def get_exponent(x):
    return ((x & 0x7f800000) >> 23) - 127

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
        af = Float32.from_bits(a)
        bf = Float32.from_bits(b)
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

def run_edge_cases(dut, count, op):
    #edge cases
    stimulus_a = [0x80000000 for i in range(1000)]
    stimulus_b = [randint(0, 1<<32) for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_a = [0x00000000 for i in range(1000)]
    stimulus_b = [randint(0, 1<<32) for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0x80000000 for i in range(1000)]
    stimulus_a = [randint(0, 1<<32) for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0x00000000 for i in range(1000)]
    stimulus_a = [randint(0, 1<<32) for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_a = [0x7F800000 for i in range(1000)]
    stimulus_b = [randint(0, 1<<32) for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_a = [0xFF800000 for i in range(1000)]
    stimulus_b = [randint(0, 1<<32) for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0x7F800000 for i in range(1000)]
    stimulus_a = [randint(0, 1<<32) for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0xFF800000 for i in range(1000)]
    stimulus_a = [randint(0, 1<<32) for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_a = [0x7FC00000 for i in range(1000)]
    stimulus_b = [randint(0, 1<<32) for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_a = [0xFFC00000 for i in range(1000)]
    stimulus_b = [randint(0, 1<<32) for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0x7FC00000 for i in range(1000)]
    stimulus_a = [randint(0, 1<<32) for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0xFFC00000 for i in range(1000)]
    stimulus_a = [randint(0, 1<<32) for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b, op)
    count += len(stimulus_a)
    print (count, "vectors passed")

    #seed(0)
    for i in range(100000):
        stimulus_a = [randint(0, 1<<32) for i in range(1000)]
        stimulus_b = [randint(0, 1<<32) for i in range(1000)]
        yield from run_test(dut, stimulus_a, stimulus_b, op)
        count += 1000
        print (count, "random vectors passed")

if __name__ == '__main__':
    dut = FPADD(width=32, single_cycle=True)
    run_simulation(dut, testbench(dut), vcd_name="test_add.vcd")

