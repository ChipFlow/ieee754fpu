from nmigen import Module, Signal
from nmigen.compat.sim import run_simulation
from operator import add

from nmigen_add_experiment import FPADD

import sys
import atexit
from random import randint
from random import seed

from unit_test_double import (get_mantissa, get_exponent, get_sign, is_nan,
                                is_inf, is_pos_inf, is_neg_inf,
                                match, get_case, check_case, run_fpunit,
                                run_edge_cases, run_corner_cases)


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
    yield from run_fpunit(dut, stimulus_a, stimulus_b, add)
    count += len(stimulus_a)
    print (count, "vectors passed")

    yield from run_corner_cases(dut, count, add)
    yield from run_edge_cases(dut, count, add)


if __name__ == '__main__':
    dut = FPADD(width=64, single_cycle=False)
    run_simulation(dut, testbench(dut), vcd_name="test_add64.vcd")

