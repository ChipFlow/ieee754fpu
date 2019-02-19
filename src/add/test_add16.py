from random import randint
from random import seed
from operator import add

from nmigen import Module, Signal
from nmigen.compat.sim import run_simulation

from nmigen_add_experiment import FPADD

from unit_test_half import (get_mantissa, get_exponent, get_sign, is_nan,
                                is_inf, is_pos_inf, is_neg_inf,
                                match, get_case, check_case, run_test,
                                run_edge_cases, run_corner_cases)

def testbench(dut):
    yield from check_case(dut, 0xfc00, 0x7c00, 0xfe00)
    yield from check_case(dut, 0x8000, 0, 0)
    yield from check_case(dut, 0, 0, 0)

    count = 0

    #regression tests
    stimulus_a = [ 0x8000 ]
    stimulus_b = [ 0x0000 ]
    yield from run_test(dut, stimulus_a, stimulus_b, add)
    count += len(stimulus_a)
    print (count, "vectors passed")

    yield from run_corner_cases(dut, count, add)
    yield from run_edge_cases(dut, count, add)

if __name__ == '__main__':
    dut = FPADD(width=16, single_cycle=True)
    run_simulation(dut, testbench(dut), vcd_name="test_add16.vcd")

