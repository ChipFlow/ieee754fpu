from nmigen import Module, Signal
from nmigen.compat.sim import run_simulation

from nmigen_add_experiment import FPADD

import sys
import atexit
from random import randint
from random import seed

from unit_test_double import (get_mantissa, get_exponent, get_sign, is_nan,
                                is_inf, is_pos_inf, is_neg_inf,
                                match, get_case, check_case, run_test)


def testbench(dut):
    yield from check_case(dut, 0, 0, 0)
    yield from check_case(dut, 0x3FF0000000000000, 0x4000000000000000,
                               0x4008000000000000)
    yield from check_case(dut, 0x4000000000000000, 0x3FF0000000000000,
                               0x4008000000000000)
    yield from check_case(dut, 0x4056C00000000000, 0x4042800000000000,
                               0x4060000000000000)
    yield from check_case(dut, 0x4056C00000000000, 0x4042EA3D70A3D70A,
                               0x40601A8F5C28F5C2)

    count = 0

    #regression tests
    stimulus_a = [0x3ff00000000000c5, 0xff80000000000000]
    stimulus_b = [0xbd28a404211fb72b, 0x7f80000000000000]
    yield from run_test(dut, stimulus_a, stimulus_b)
    count += len(stimulus_a)
    print (count, "vectors passed")

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
    yield from run_test(dut, stimulus_a, stimulus_b)
    count += len(stimulus_a)
    print (count, "vectors passed")

    #edge cases
    stimulus_a = [0x8000000000000000 for i in range(1000)]
    stimulus_b = [randint(0, 1<<64)  for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_a = [0x0000000000000000 for i in range(1000)]
    stimulus_b = [randint(0, 1<<64)  for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0x8000000000000000 for i in range(1000)]
    stimulus_a = [randint(0, 1<<64)  for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0x0000000000000000 for i in range(1000)]
    stimulus_a = [randint(0, 1<<64)  for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_a = [0x7FF8000000000000 for i in range(1000)]
    stimulus_b = [randint(0, 1<<64)  for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_a = [0xFFF8000000000000 for i in range(1000)]
    stimulus_b = [randint(0, 1<<64)  for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0x7FF8000000000000 for i in range(1000)]
    stimulus_a = [randint(0, 1<<64) for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0xFFF8000000000000 for i in range(1000)]
    stimulus_a = [randint(0, 1<<64) for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_a = [0x7FF0000000000000 for i in range(1000)]
    stimulus_b = [randint(0, 1<<64)  for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_a = [0xFFF0000000000000 for i in range(1000)]
    stimulus_b = [randint(0, 1<<64)  for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0x7FF0000000000000 for i in range(1000)]
    stimulus_a = [randint(0, 1<<64)  for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b)
    count += len(stimulus_a)
    print (count, "vectors passed")

    stimulus_b = [0xFFF0000000000000 for i in range(1000)]
    stimulus_a = [randint(0, 1<<64)  for i in range(1000)]
    yield from run_test(dut, stimulus_a, stimulus_b)
    count += len(stimulus_a)
    print (count, "vectors passed")

    #seed(0)
    for i in range(100000):
        stimulus_a = [randint(0, 1<<64) for i in range(1000)]
        stimulus_b = [randint(0, 1<<64) for i in range(1000)]
        yield from run_test(dut, stimulus_a, stimulus_b)
        count += 1000
        print (count, "random vectors passed")


if __name__ == '__main__':
    dut = FPADD(width=64, single_cycle=True)
    run_simulation(dut, testbench(dut), vcd_name="test_add64.vcd")

