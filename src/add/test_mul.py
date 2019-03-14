import sys
from random import randint
from random import seed
from operator import mul

from nmigen import Module, Signal
from nmigen.compat.sim import run_simulation

from fmul import FPMUL

from unit_test_single import (get_mantissa, get_exponent, get_sign, is_nan,
                                is_inf, is_pos_inf, is_neg_inf,
                                match, get_case, check_case, run_test,
                                run_edge_cases, run_corner_cases)


def testbench(dut):
    yield from check_case(dut, 0x40000000, 0x40000000, 0x40800000)
    yield from check_case(dut, 0x41400000, 0x40A00000, 0x42700000)

    count = 0

    #regression tests
    stimulus_a = [0xba57711a, 0xbf9b1e94, 0x34082401, 0x5e8ef81,
                  0x5c75da81, 0x2b017]
    stimulus_b = [0xee1818c5, 0xc038ed3a, 0xb328cd45, 0x114f3db,
                  0x2f642a39, 0xff3807ab]
    yield from run_test(dut, stimulus_a, stimulus_b, mul, get_case)
    count += len(stimulus_a)
    print (count, "vectors passed")

    yield from run_corner_cases(dut, count, mul, get_case)
    yield from run_edge_cases(dut, count, mul, get_case)


if __name__ == '__main__':
    dut = FPMUL(width=32)
    run_simulation(dut, testbench(dut), vcd_name="test_mul.vcd")

