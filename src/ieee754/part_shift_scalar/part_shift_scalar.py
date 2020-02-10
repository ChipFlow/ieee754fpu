# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

"""
Copyright (C) 2020 Luke Kenneth Casson Leighton <lkcl@lkcl.net>
Copyright (C) 2020 Michael Nolan <mtnolan2640@gmail.com>

dynamically-partitionable "comparison" class, directly equivalent
to Signal.__eq__, __gt__ and __ge__, except SIMD-partitionable

See:

* http://libre-riscv.org/3d_gpu/architecture/dynamic_simd/shift/
* http://bugs.libre-riscv.org/show_bug.cgi?id=173
"""
from nmigen import Signal, Module, Elaboratable, Cat, Mux
from ieee754.part_mul_add.partpoints import PartitionPoints
import math


class PartitionedScalarShift(Elaboratable):
    def __init__(self, width, partition_points):
        self.width = width
        self.partition_points = PartitionPoints(partition_points)

        self.data = Signal(width)
        self.shiftbits = math.ceil(math.log2(width))
        self.shifter = Signal(self.shiftbits)
        self.output = Signal(width)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        width = self.width
        shiftbits = self.shiftbits
        shifted = Signal(self.data.width)
        gates = self.partition_points.as_sig()
        comb += shifted.eq(self.data << self.shifter)

        parts = []
        outputs = []
        shiftparts = []
        intervals = []
        keys = list(self.partition_points.keys()) + [self.width]
        start = 0
        for i in range(len(keys)):
            end = keys[i]
            parts.append(self.data[start:end])
            outputs.append(self.output[start:end])
            intervals.append((start,end))

            sp = Signal(width)
            comb += sp[start:].eq(self.data[start:end] << self.shifter)
            shiftparts.append(sp)
            
            start = end  # for next time round loop

        for i, interval in enumerate(intervals):
            start, end = interval
            if i == 0:
                intermed = shiftparts[i]
            else:
                intermed = shiftparts[i] | Mux(gates[i-1], 0, prev)
            comb += outputs[i].eq(intermed[start:end])
            prev = intermed

        return m
