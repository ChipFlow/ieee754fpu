from nmigen import Module, Signal
from nmigen.compat.sim import run_simulation
from operator import truediv

from ieee754.fpdiv.nmigen_div_experiment import FPDIV

from ieee754.fpcommon.test.unit_test_double import (get_mantissa,
                                get_exponent, get_sign, is_nan,
                                is_inf, is_pos_inf, is_neg_inf,
                                match, get_case, check_case, run_fpunit,
                                run_edge_cases, run_corner_cases)

def testbench(dut):
    yield from check_case(dut, 0x4008000000000000, 0x3FF0000000000000,
                               0x4008000000000000)
    yield from check_case(dut, 0x3FF0000000000000, 0x4008000000000000,
                               0x3FD5555555555555)

    count = 0

    #regression tests
    #stimulus_a = [0xbf9b1e94, 0x34082401, 0x5e8ef81, 0x5c75da81, 0x2b017]
    #stimulus_b = [0xc038ed3a, 0xb328cd45, 0x114f3db, 0x2f642a39, 0xff3807ab]
    #yield from run_fpunit(dut, stimulus_a, stimulus_b, truediv, get_case)
    #count += len(stimulus_a)
    #print (count, "vectors passed")

    yield from run_corner_cases(dut, count, truediv, get_case)
    yield from run_edge_cases(dut, count, truediv, get_case)


if __name__ == '__main__':
    dut = FPDIV(width=64)
    run_simulation(dut, testbench(dut), vcd_name="test_div64.vcd")

