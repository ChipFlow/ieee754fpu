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


class PartitionedXOR(Elaboratable):

    def __init__(self, width, partition_points):
        """Create a ``PartitionedXOR`` operator
        """
        self.width = width
        self.a = Signal(width, reset_less=True)
        self.partition_points = PartitionPoints(partition_points)
        self.mwidth = len(self.partition_points)+1
        self.output = Signal(self.mwidth, reset_less=True)
        if not self.partition_points.fits_in_width(width):
            raise ValueError("partition_points doesn't fit in width")

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        m.submodules.xorc = xorc = XORCombiner(self.mwidth)

        # make a series of "xor", splitting a and b into partition chunks
        xors = Signal(self.mwidth, reset_less=True)
        xorl = []
        keys = list(self.partition_points.keys()) + [self.width]
        start = 0
        for i in range(len(keys)):
            end = keys[i]
            xorl.append(self.a[start:end].xor())
            start = end # for next time round loop
        comb += xors.eq(Cat(*xorl))

        # put the partial results through the combiner
        comb += xorc.gates.eq(self.partition_points.as_sig())
        comb += xorc.neqs.eq(xors)

        m.submodules.ripple = ripple = RippleLSB(self.mwidth)
        comb += ripple.results_in.eq(xorc.outputs)
        comb += ripple.gates.eq(self.partition_points.as_sig())
        comb += self.output.eq(~ripple.output)

        return m

    def ports(self):
        return [self.a, self.output]


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

