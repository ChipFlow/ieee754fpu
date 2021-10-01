# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

"""
Copyright (C) 2020,2021 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

dynamically-partitionable "sig" class, directly equivalent
to Signal.sig() except SIMD-partitionable

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


class PartitionedBase(Elaboratable):

    def __init__(self, width, partition_points, CombinerKls, operator):
        """Create a ``PartitionedBool`` operator
        """
        self.width = width
        self.a = Signal(width, reset_less=True)
        self.partition_points = PartitionPoints(partition_points)
        self.mwidth = len(self.partition_points)+1
        self.output = Signal(self.mwidth, reset_less=True)
        self.combiner_kls = CombinerKls
        self.operator = operator
        if not self.partition_points.fits_in_width(width):
            raise ValueError("partition_points doesn't fit in width")

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        m.submodules.sigc = sigc = self.combiner_kls(self.mwidth)

        # make a series of "sig", splitting a and b into partition chunks
        sigs = Signal(self.mwidth, reset_less=True)
        sigl = []
        keys = list(self.partition_points.keys()) + [self.width]
        start = 0
        for i in range(len(keys)):
            end = keys[i]
            part = self.a[start:end]
            part = getattr(part, self.operator)()
            sigl.append(part)
            start = end # for next time round loop
        comb += sigs.eq(Cat(*sigl))

        # put the partial results through the combiner
        comb += sigc.gates.eq(self.partition_points.as_sig())
        comb += sigc.neqs.eq(sigs)

        m.submodules.ripple = ripple = RippleLSB(self.mwidth)
        comb += ripple.results_in.eq(sigc.outputs)
        comb += ripple.gates.eq(self.partition_points.as_sig())
        comb += self.output.eq(~ripple.output)

        return m

    def ports(self):
        return [self.a, self.output]


