# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

"""
Copyright (C) 2020 Luke Kenneth Casson Leighton <lkcl@lkcl.net>
Copyright (C) 2020 Michael Nolan <mtnolan2640@gmail.com>

dynamically partitionable shifter. Unlike part_shift_scalar, both
operands can be partitioned

See:

* http://libre-riscv.org/3d_gpu/architecture/dynamic_simd/shift/
* http://bugs.libre-riscv.org/show_bug.cgi?id=173
"""
from nmigen import Signal, Module, Elaboratable, Cat, Mux
from ieee754.part_mul_add.partpoints import PartitionPoints
import math


class PartitionedDynamicShift(Elaboratable):
    def __init__(self, width, partition_points):
        self.width = width
        self.partition_points = PartitionPoints(partition_points)

        self.a = Signal(width)
        self.b = Signal(width)
        self.output = Signal(width)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        width = self.width
        gates = self.partition_points.as_sig()

        matrix = []
        keys = list(self.partition_points.keys()) + [self.width]
        start = 0

        for i in range(len(keys)):
            row = []
            start = 0
            for i in range(len(keys)):
                end = keys[i]
                row.append(Signal(width - start))
            matrix.append(row)

        a_intervals = []
        b_intervals = []
        out_intervals = []
        intervals = []
        start = 0
        for i in range(len(keys)):
            end = keys[i]
            a_intervals.append(self.a[start:end])
            b_intervals.append(self.b[start:end])
            out_intervals.append(self.output[start:end])
            intervals.append([start,end])
            start = end

        for i, b in enumerate(b_intervals):
            start = 0
            for j, a in enumerate(a_intervals):
                end = keys[i]
                comb += matrix[i][j].eq(a << b)
                start = end

        intermed = matrix[0][0]
        comb += out_intervals[0].eq(intermed)
        for i in range(1, len(out_intervals)):
            index = gates[:i]  # selects the 'i' least significant bits
                               # of gates
            for index in range(1<<(i-1)):
                with m.Switch(gates[:i]):
                    with m.Case(index):
                        element = matrix[index][i]
            print(keys[i-1])
            intermed = Mux(gates[i-1], element, element | intermed[:keys[i-1]])
            comb += out_intervals[i].eq(intermed)


        return m

