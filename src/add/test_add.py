import sys
import subprocess
from random import randint
from random import seed
from sfpy import Float32

from nmigen import Module, Signal
from nmigen.compat.sim import run_simulation

from nmigen_add_experiment import FPADD

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


def run_test(dut, stimulus_a, stimulus_b):

    expected_responses = []
    actual_responses = []
    for a, b in zip(stimulus_a, stimulus_b):
        af = Float32.from_bits(a)
        bf = Float32.from_bits(b)
        z = af + bf
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

def testbench(dut):
    yield from check_case(dut, 0xfe34f995, 0xff5d59ad, 0xff800000)
    yield from check_case(dut, 0x82471f51, 0x243985f, 0x801c3790)
    yield from check_case(dut, 0, 0, 0)
    yield from check_case(dut, 0x40000000, 0xc0000000, 0x00000000)
    yield from check_case(dut, 0x3F800000, 0x40000000, 0x40400000)
    yield from check_case(dut, 0x40000000, 0x3F800000, 0x40400000)
    yield from check_case(dut, 0x447A0000, 0x4488B000, 0x4502D800)
    yield from check_case(dut, 0x463B800A, 0x42BA8A3D, 0x463CF51E)
    yield from check_case(dut, 0x42BA8A3D, 0x463B800A, 0x463CF51E)
    yield from check_case(dut, 0x463B800A, 0xC2BA8A3D, 0x463A0AF6)
    yield from check_case(dut, 0xC2BA8A3D, 0x463B800A, 0x463A0AF6)
    yield from check_case(dut, 0xC63B800A, 0x42BA8A3D, 0xC63A0AF6)
    yield from check_case(dut, 0x42BA8A3D, 0xC63B800A, 0xC63A0AF6)
    yield from check_case(dut, 0xFFFFFFFF, 0xC63B800A, 0xFFC00000)
    yield from check_case(dut, 0x7F800000, 0x00000000, 0x7F800000)
    yield from check_case(dut, 0x00000000, 0x7F800000, 0x7F800000)
    yield from check_case(dut, 0xFF800000, 0x00000000, 0xFF800000)
    yield from check_case(dut, 0x00000000, 0xFF800000, 0xFF800000)
    yield from check_case(dut, 0x7F800000, 0x7F800000, 0x7F800000)
    yield from check_case(dut, 0xFF800000, 0xFF800000, 0xFF800000)
    yield from check_case(dut, 0x7F800000, 0xFF800000, 0xFFC00000)
    yield from check_case(dut, 0xFF800000, 0x7F800000, 0x7FC00000)
    yield from check_case(dut, 0x00018643, 0x00FA72A4, 0x00FBF8E7)
    yield from check_case(dut, 0x001A2239, 0x00FA72A4, 0x010A4A6E)
    yield from check_case(dut, 0x3F7FFFFE, 0x3F7FFFFE, 0x3FFFFFFE)
    yield from check_case(dut, 0x7EFFFFEE, 0x7EFFFFEE, 0x7F7FFFEE)
    yield from check_case(dut, 0x7F7FFFEE, 0xFEFFFFEE, 0x7EFFFFEE)
    yield from check_case(dut, 0x7F7FFFEE, 0x756CA884, 0x7F7FFFFD)
    yield from check_case(dut, 0x7F7FFFEE, 0x758A0CF8, 0x7F7FFFFF)
    yield from check_case(dut, 0x42500000, 0x51A7A358, 0x51A7A358)
    yield from check_case(dut, 0x51A7A358, 0x42500000, 0x51A7A358)
    yield from check_case(dut, 0x4E5693A4, 0x42500000, 0x4E5693A5)
    yield from check_case(dut, 0x42500000, 0x4E5693A4, 0x4E5693A5)
    #yield from check_case(dut, 1, 0, 1)
    #yield from check_case(dut, 1, 1, 1)

    count = 0

    #regression tests
    stimulus_a = [0x22cb525a, 0x40000000, 0x83e73d5c, 0xbf9b1e94, 0x34082401, 0x5e8ef81, 0x5c75da81, 0x2b017]
    stimulus_b = [0xadd79efa, 0xC0000000, 0x1c800000, 0xc038ed3a, 0xb328cd45, 0x114f3db, 0x2f642a39, 0xff3807ab]
    yield from run_test(dut, stimulus_a, stimulus_b)
    count += len(stimulus_a)
    print (count, "vectors passed")

    #corner cases
    from itertools import permutations
    stimulus_a = [i[0] for i in permutations([0x80000000, 0x00000000, 0x7f800000, 0xff800000, 0x7fc00000, 0xffc00000], 2)]
    stimulus_b = [i[1] for i in permutations([0x80000000, 0x00000000, 0x7f800000, 0xff800000, 0x7fc00000, 0xffc00000], 2)]
    yield from run_test(dut, stimulus_a, stimulus_b)
    count += len(stimulus_a)
    print (count, "vectors passed")

    #edge cases
    stimulus_a = [0x80000000 for i in range(1000)]
    stimulus_b = [randint(0, 1<<32) for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_a = [0x00000000 for i in range(1000)]
    stimulus_b = [randint(0, 1<<32) for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0x80000000 for i in range(1000)]
    stimulus_a = [randint(0, 1<<32) for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0x00000000 for i in range(1000)]
    stimulus_a = [randint(0, 1<<32) for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_a = [0x7F800000 for i in range(1000)]
    stimulus_b = [randint(0, 1<<32) for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_a = [0xFF800000 for i in range(1000)]
    stimulus_b = [randint(0, 1<<32) for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0x7F800000 for i in range(1000)]
    stimulus_a = [randint(0, 1<<32) for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0xFF800000 for i in range(1000)]
    stimulus_a = [randint(0, 1<<32) for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_a = [0x7FC00000 for i in range(1000)]
    stimulus_b = [randint(0, 1<<32) for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_a = [0xFFC00000 for i in range(1000)]
    stimulus_b = [randint(0, 1<<32) for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0x7FC00000 for i in range(1000)]
    stimulus_a = [randint(0, 1<<32) for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0xFFC00000 for i in range(1000)]
    stimulus_a = [randint(0, 1<<32) for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b)
    count += len(stimulus_a)
    print (count, "vectors passed")

    #seed(0)
    for i in range(100000):
        stimulus_a = [randint(0, 1<<32) for i in range(1000)]
        stimulus_b = [randint(0, 1<<32) for i in range(1000)]
        yield from run_test(dut, stimulus_a, stimulus_b)
        count += 1000
        print (count, "random vectors passed")

if __name__ == '__main__':
    dut = FPADD(width=32, single_cycle=True)
    run_simulation(dut, testbench(dut), vcd_name="test_add.vcd")

