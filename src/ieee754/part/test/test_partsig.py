#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

from nmigen import Signal, Module, Elaboratable
from nmigen.back.pysim import Simulator, Delay, Tick, Passive
from nmigen.cli import verilog, rtlil

from ieee754.part.partsig import PartitionedSignal

import unittest

def create_ilang(dut, traces, test_name):
    vl = rtlil.convert(dut, ports=traces)
    with open("%s.il" % test_name, "w") as f:
        f.write(vl)


def create_simulator(module, traces, test_name):
    create_ilang(module, traces, test_name)
    return Simulator(module,
                     vcd_file=open(test_name + ".vcd", "w"),
                     gtkw_file=open(test_name + ".gtkw", "w"),
                     traces=traces)

class TestAddMod(Elaboratable):
    def __init__(self, width, partpoints):
        self.a = PartitionedSignal(partpoints, width)
        self.b = PartitionedSignal(partpoints, width)
        self.add_output = Signal(width)
        self.eq_output = Signal(len(partpoints)+1)

    def elaborate(self, platform):
        m = Module()
        self.a.set_module(m)
        self.b.set_module(m)
        m.d.comb += self.eq_output.eq(self.a == self.b)
        m.d.comb += self.add_output.eq(self.a + self.b)

        return m


class TestPartitionPoints(unittest.TestCase):
    def test(self):
        width = 16
        part_mask = Signal(4) # divide into 4-bits
        module = TestAddMod(width, part_mask)

        sim = create_simulator(module,
                              [part_mask,
                               module.a.sig,
                               module.b.sig,
                               module.add_output,
                               module.eq_output],
                              "part_sig_add")
        def async_process():
            def test_add(msg_prefix, *mask_list):
                for a, b in [(0x0000, 0x0000),
                             (0x1234, 0x1234),
                             (0xABCD, 0xABCD),
                             (0xFFFF, 0x0000),
                             (0x0000, 0x0000),
                             (0xFFFF, 0xFFFF),
                             (0x0000, 0xFFFF)]:
                    yield module.a.eq(a)
                    yield module.b.eq(b)
                    yield Delay(0.1e-6)
                    y = 0
                    for mask in mask_list:
                        y |= mask & ((a & mask) + (b & mask))
                    outval = (yield module.add_output)
                    msg = f"{msg_prefix}: 0x{a:X} + 0x{b:X}" + \
                        f" => 0x{y:X} != 0x{outval:X}"
                    self.assertEqual(y, outval, msg)
            yield part_mask.eq(0)
            yield from test_add("16-bit", 0xFFFF)
            yield part_mask.eq(0b10)
            yield from test_add("8-bit", 0xFF00, 0x00FF)
            yield part_mask.eq(0b1111)
            yield from test_add("4-bit", 0xF000, 0x0F00, 0x00F0, 0x000F)

            def test_eq(msg_prefix, *maskbit_list):
                for a, b in [(0x0000, 0x0000),
                             (0x1234, 0x1234),
                             (0xABCD, 0xABCD),
                             (0xFFFF, 0x0000),
                             (0x0000, 0x0000),
                             (0xFFFF, 0xFFFF),
                             (0x0000, 0xFFFF)]:
                    yield module.a.eq(a)
                    yield module.b.eq(b)
                    yield Delay(0.1e-6)
                    # convert to mask_list
                    mask_list = []
                    for b in maskbit_list:
                        v = 0
                        for i in range(4):
                            if b & (1<<i):
                                v |= 0xf << (i*4)
                        mask_list.append(v)
                    y = 0
                    for i, mask in enumerate(mask_list):
                        if (a & mask) == (b & mask):
                            y |= maskbit_list[i]
                    outval = (yield module.eq_output)
                    msg = f"{msg_prefix}: 0x{a:X} + 0x{b:X}" + \
                        f" => 0x{y:X} != 0x{outval:X}, masklist %s"
                    self.assertEqual(y, outval, msg % str(maskbit_list))
            yield part_mask.eq(0)
            yield from test_eq("16-bit", 0b1111)
            yield part_mask.eq(0b10)
            yield from test_eq("8-bit", 0b1100, 0b0011)
            yield part_mask.eq(0b1111)
            yield from test_eq("4-bit", 0b1000, 0b0100, 0b0010, 0b0001)

        sim.add_process(async_process)
        sim.run()

if __name__ == '__main__':
    unittest.main()

