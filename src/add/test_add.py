from operator import add

from nmigen import Module, Signal
from nmigen.compat.sim import run_simulation

from nmigen_add_experiment import FPADD

from unit_test_single import (get_mantissa, get_exponent, get_sign, is_nan,
                                is_inf, is_pos_inf, is_neg_inf,
                                match, get_case, check_case, run_test,
                                run_edge_cases, run_corner_cases)

def testbench(dut):
    yield from check_case(dut, 0x36093399, 0x7f6a12f1, 0x7f6a12f1)
    yield from check_case(dut, 0x006CE3EE, 0x806CE3EC, 0x00000002)
    yield from check_case(dut, 0x00000047, 0x80000048, 0x80000001)
    yield from check_case(dut, 0x000116C2, 0x8001170A, 0x80000048)
    yield from check_case(dut, 0x7ed01f25, 0xff559e2c, 0xfedb1d33)
    yield from check_case(dut, 0, 0, 0)
    yield from check_case(dut, 0xFFFFFFFF, 0xC63B800A, 0x7FC00000)
    yield from check_case(dut, 0xFF800000, 0x7F800000, 0x7FC00000)
    #yield from check_case(dut, 0xFF800000, 0x7F800000, 0x7FC00000)
    yield from check_case(dut, 0x7F800000, 0xFF800000, 0x7FC00000)
    yield from check_case(dut, 0x42540000, 0xC2540000, 0x00000000)
    yield from check_case(dut, 0xC2540000, 0x42540000, 0x00000000)
    yield from check_case(dut, 0xfe34f995, 0xff5d59ad, 0xff800000)
    yield from check_case(dut, 0x82471f51, 0x243985f, 0x801c3790)
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
    yield from check_case(dut, 0x7F800000, 0x00000000, 0x7F800000)
    yield from check_case(dut, 0x00000000, 0x7F800000, 0x7F800000)
    yield from check_case(dut, 0xFF800000, 0x00000000, 0xFF800000)
    yield from check_case(dut, 0x00000000, 0xFF800000, 0xFF800000)
    yield from check_case(dut, 0x7F800000, 0x7F800000, 0x7F800000)
    yield from check_case(dut, 0xFF800000, 0xFF800000, 0xFF800000)
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
    stimulus_a = [0x80000000, 0x22cb525a, 0x40000000, 0x83e73d5c,
                  0xbf9b1e94, 0x34082401,
                    0x5e8ef81, 0x5c75da81, 0x2b017]
    stimulus_b = [0xff800001, 0xadd79efa, 0xC0000000, 0x1c800000,
                  0xc038ed3a, 0xb328cd45, 
                    0x114f3db, 0x2f642a39, 0xff3807ab]
    yield from run_test(dut, stimulus_a, stimulus_b, add)
    count += len(stimulus_a)
    print (count, "vectors passed")

    yield from run_corner_cases(dut, count, add)
    yield from run_edge_cases(dut, count, add)

if __name__ == '__main__':
    dut = FPADD(width=32, single_cycle=True)
    run_simulation(dut, testbench(dut), vcd_name="test_add.vcd")

