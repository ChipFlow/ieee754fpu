import sys
from random import randint
from random import seed
from operator import truediv

from nmigen import Module, Signal
from nmigen.compat.sim import run_simulation

from ieee754.fpdiv.nmigen_div_experiment import FPDIV

from ieee754.fpcommon.test.unit_test_single import (get_mantissa,
                                get_exponent, get_sign, is_nan,
                                is_inf, is_pos_inf, is_neg_inf,
                                match, get_case, check_case, run_fpunit,
                                run_edge_cases, run_corner_cases)


def testbench(dut):
    yield from check_case(dut, 0x80000000, 0x00000000, 0xffc00000)
    yield from check_case(dut, 0x00000000, 0x80000000, 0xffc00000)
    yield from check_case(dut, 0x0002b017, 0xff3807ab, 0x80000000)
    yield from check_case(dut, 0x40000000, 0x3F800000, 0x40000000)
    yield from check_case(dut, 0x3F800000, 0x40000000, 0x3F000000)
    yield from check_case(dut, 0x3F800000, 0x40400000, 0x3EAAAAAB)
    yield from check_case(dut, 0x40400000, 0x41F80000, 0x3DC6318C)
    yield from check_case(dut, 0x41F9EB4D, 0x429A4C70, 0x3ECF52B2)
    yield from check_case(dut, 0x7F7FFFFE, 0x70033181, 0x4EF9C4C8)
    yield from check_case(dut, 0x7F7FFFFE, 0x70000001, 0x4EFFFFFC)
    yield from check_case(dut, 0x7F7FFCFF, 0x70200201, 0x4ECCC7D5)
    yield from check_case(dut, 0x70200201, 0x7F7FFCFF, 0x302003E2)

    count = 0

    #regression tests
    stimulus_a = [0xbf9b1e94, 0x34082401, 0x5e8ef81, 0x5c75da81, 0x2b017]
    stimulus_b = [0xc038ed3a, 0xb328cd45, 0x114f3db, 0x2f642a39, 0xff3807ab]
    yield from run_fpunit(dut, stimulus_a, stimulus_b, truediv, get_case)
    count += len(stimulus_a)
    print (count, "vectors passed")

    yield from run_corner_cases(dut, count, truediv, get_case)
    yield from run_edge_cases(dut, count, truediv, get_case)


if __name__ == '__main__':
    dut = FPDIV(width=32)
    run_simulation(dut, testbench(dut), vcd_name="test_div.vcd")

