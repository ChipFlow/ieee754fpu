#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

from ieee754.part.partsig import PartitionedSignal
from nmigen import Signal, Module, Elaboratable
from nmigen.back.pysim import Simulator, Delay, Tick, Passive
from nmigen.cli import verilog, rtlil

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

    def elaborate(self, platform):
        m = Module()
        m.submodules.a = self.a
        m.submodules.b = self.b
        m.d.comb += self.add_output.eq(self.a + self.b)

        return m


class TestPartitionPoints(unittest.TestCase):
    def test(self):
        width = 16
        partition_nibbles = Signal() # divide into 4-bits
        partition_bytes = Signal()   # divide on 8-bits
        partpoints = {0x4: partition_nibbles,
                      0x8: partition_bytes | partition_nibbles,
                      0xC: partition_nibbles}
        module = TestAddMod(width, partpoints)

        sim = create_simulator(module,
                              [partition_nibbles,
                               partition_bytes,
                               module.a.sig,
                               module.b.sig,
                               module.add_output],
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
            yield partition_nibbles.eq(0)
            yield partition_bytes.eq(0)
            yield from test_add("16-bit", 0xFFFF)
            yield partition_nibbles.eq(0)
            yield partition_bytes.eq(1)
            yield from test_add("8-bit", 0xFF00, 0x00FF)
            yield partition_nibbles.eq(1)
            yield partition_bytes.eq(0)
            yield from test_add("4-bit", 0xF000, 0x0F00, 0x00F0, 0x000F)

        sim.add_process(async_process)
        sim.run()

if __name__ == '__main__':
    unittest.main()

