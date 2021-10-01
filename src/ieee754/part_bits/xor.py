# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

"""
Copyright (C) 2020 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

dynamically-partitionable "xor" class, directly equivalent
to Signal.xor() except SIMD-partitionable

See:

* http://libre-riscv.org/3d_gpu/architecture/dynamic_simd/logicops
* http://bugs.libre-riscv.org/show_bug.cgi?id=176
"""

from nmigen import Signal, Module, Elaboratable, Cat, C
from nmigen.back.pysim import Simulator, Settle
from nmigen.cli import rtlil
from nmutil.ripple import RippleLSB

from ieee754.part_mul_add.partpoints import PartitionPoints
from ieee754.part_cmp.experiments.eq_combiner import XORCombiner
from ieee754.part_bits.base import PartitionedBase



class PartitionedXOR(PartitionedBase):

    def __init__(self, width, partition_points):
        """Create a ``PartitionedXOR`` operator
        """
        super().__init__(width, partition_points, XORCombiner, "xor")


if __name__ == "__main__":

    from ieee754.part_mul_add.partpoints import make_partition
    m = Module()
    mask = Signal(4)
    m.submodules.xor = xor = PartitionedXOR(16, make_partition(mask, 16))

    vl = rtlil.convert(xor, ports=xor.ports())
    with open("part_xor.il", "w") as f:
        f.write(vl)

    sim = Simulator(m)

    def process():
        yield mask.eq(0b010)
        yield xor.a.eq(0x8c14)
        yield Settle()
        out = yield xor.output
        m = yield mask
        print("out", bin(out), "mask", bin(m))
        yield mask.eq(0b111)
        yield Settle()
        out = yield xor.output
        m = yield mask
        print("out", bin(out), "mask", bin(m))
        yield mask.eq(0b010)
        yield Settle()
        out = yield xor.output
        m = yield mask
        print("out", bin(out), "mask", bin(m))

    sim.add_process(process)
    with sim.write_vcd("part_xor.vcd", "part_xor.gtkw", traces=xor.ports()):
        sim.run()

