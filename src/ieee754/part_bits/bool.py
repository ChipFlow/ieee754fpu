# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

"""
Copyright (C) 2020,2021 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

dynamically-partitionable "bool" class, directly equivalent
to Signal.bool() except SIMD-partitionable

See:

* http://libre-riscv.org/3d_gpu/architecture/dynamic_simd/logicops
* http://bugs.libre-riscv.org/show_bug.cgi?id=176
"""

from nmigen import Signal, Module, Elaboratable, Cat, C
from nmigen.back.pysim import Simulator, Settle
from nmigen.cli import rtlil
from nmutil.ripple import RippleLSB

from ieee754.part_mul_add.partpoints import PartitionPoints
from ieee754.part_cmp.experiments.eq_combiner import EQCombiner
from ieee754.part_bits.base import PartitionedBase


class PartitionedBool(PartitionedBase):

    def __init__(self, width, partition_points):
        """Create a ``PartitionedBool`` operator
        """
        super().__init__(width, partition_points, EQCombiner, "bool")


if __name__ == "__main__":

    from ieee754.part_mul_add.partpoints import make_partition
    m = Module()
    mask = Signal(4)
    m.submodules.mbool = mbool = PartitionedBool(16, make_partition(mask, 16))

    vl = rtlil.convert(mbool, ports=mbool.ports())
    with open("part_bool.il", "w") as f:
        f.write(vl)

    sim = Simulator(m)

    def process():
        yield mask.eq(0b010)
        yield mbool.a.eq(0x80c4)
        yield Settle()
        out = yield mbool.output
        m = yield mask
        a = yield mbool.a
        print("in", hex(a), "out", bin(out), "mask", bin(m))

        yield mask.eq(0b111)
        yield Settle()
        out = yield mbool.output
        m = yield mask
        a = yield mbool.a
        print("in", hex(a), "out", bin(out), "mask", bin(m))

        yield mask.eq(0b010)
        yield Settle()
        out = yield mbool.output
        m = yield mask
        a = yield mbool.a
        print("in", hex(a), "out", bin(out), "mask", bin(m))

        yield mask.eq(0b000)
        yield mbool.a.eq(0x0300)
        yield Settle()
        out = yield mbool.output
        m = yield mask
        a = yield mbool.a
        print("in", hex(a), "out", bin(out), "mask", bin(m))

        yield mask.eq(0b010)
        yield Settle()
        out = yield mbool.output
        m = yield mask
        a = yield mbool.a
        print("in", hex(a), "out", bin(out), "mask", bin(m))

        yield mask.eq(0b111)
        yield Settle()
        out = yield mbool.output
        m = yield mask
        a = yield mbool.a
        print("in", hex(a), "out", bin(out), "mask", bin(m))

        yield mask.eq(0b010)
        yield Settle()
        out = yield mbool.output
        m = yield mask
        a = yield mbool.a
        print("in", hex(a), "out", bin(out), "mask", bin(m))

    sim.add_process(process)
    with sim.write_vcd("part_bool.vcd", "part_bool.gtkw", traces=mbool.ports()):
        sim.run()

