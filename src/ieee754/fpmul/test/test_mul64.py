from nmigen import Module, Signal
from nmigen.compat.sim import run_simulation
from operator import mul

from fmul import FPMUL

import sys
import atexit
from random import randint
from random import seed

from unit_test_double import (get_mantissa, get_exponent, get_sign, is_nan,
                                is_inf, is_pos_inf, is_neg_inf,
                                match, get_case, check_case, run_test,
                                run_edge_cases, run_corner_cases)


def testbench(dut):
    yield from check_case(dut, 0, 0, 0)

    count = 0

    #regression tests
    stimulus_a = [0xff80000000000000, 0x3351099a0528e138]
    stimulus_b = [0x7f80000000000000, 0xd651a9a9986af2b5]
    yield from run_test(dut, stimulus_a, stimulus_b, mul)
    count += len(stimulus_a)
    print (count, "vectors passed")

    yield from run_corner_cases(dut, count, mul)
    yield from run_edge_cases(dut, count, mul)


if __name__ == '__main__':
    dut = FPMUL(width=64)
    run_simulation(dut, testbench(dut), vcd_name="test_mul64.vcd")

