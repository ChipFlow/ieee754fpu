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
    #yield from check_case(dut, 0x7800, 0xff6f, 0xff6f)
    #yield from check_case(dut, 0x0000, 0x7c32, 0x7e32)
    #yield from check_case(dut, 0x0000, 0x7da9, 0x7fa9)
    #yield from check_case(dut, 0x0000, 0x7ea0, 0x7ea0)
    #yield from check_case(dut, 0x7c9a, 0x8000, 0x7e9a)
    #yield from check_case(dut, 0x7d5e, 0x0000, 0x7f5e)
    #yield from check_case(dut, 0x8000, 0x7c8c, 0x7e8c)
    #yield from check_case(dut, 0x8000, 0xfc55, 0xfe55)
    #yield from check_case(dut, 0x8000, 0x7e1a, 0x7e1a)
    #yield from check_case(dut, 0xfc00, 0x7c00, 0xfe00)
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
    dut = FPADD(width=16, single_cycle=False)
    run_simulation(dut, testbench(dut), vcd_name="test_add16.vcd")

