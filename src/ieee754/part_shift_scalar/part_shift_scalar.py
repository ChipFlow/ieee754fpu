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
from nmigen import Signal, Module, Elaboratable, Cat, C
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
        comb += shifted.eq(self.data << self.shifter)

        comb += self.output[0:8].eq(shifted[0:8])
        comb += self.output[8:16].eq(shifted[8:16])

        return m
        
    
