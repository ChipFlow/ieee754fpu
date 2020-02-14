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
from nmigen import Signal, Module, Elaboratable, Cat, Mux, C
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
        gates = Signal(self.partition_points.get_max_partition_count(width)-1)
        comb += gates.eq(self.partition_points.as_sig())

        matrix = []
        keys = list(self.partition_points.keys()) + [self.width]
        start = 0


        # break out both the input and output into partition-stratified blocks
        a_intervals = []
        b_intervals = []
        out_intervals = []
        intervals = []
        widths = []
        start = 0
        for i in range(len(keys)):
            end = keys[i]
            widths.append(width - start)
            a_intervals.append(self.a[start:end])
            b_intervals.append(self.b[start:end])
            out_intervals.append(self.output[start:end])
            intervals.append([start,end])
            start = end

        # Instead of generating the matrix described in the wiki, I
        # instead calculate the shift amounts for each partition, then
        # calculate the partial results of each partition << shift
        # amount. On the wiki, the following table is given for output #3:
        # p2p1p0 | o3
        # 0 0 0  | a0b0[31:24] | a1b0[23:16] | a2b0[15:8] | a3b0[7:0]
        # 0 0 1  | a0b0[31:24] | a1b1[23:16] | a2b1[15:8] | a3b1[7:0]
        # 0 1 0  | a0b0[31:24] | a1b0[23:16] | a2b2[15:8] | a3b2[7:0]
        # 0 1 1  | a0b0[31:24] | a1b1[23:16] | a2b2[15:8] | a3b2[7:0]
        # 1 0 0  | a0b0[31:24] | a1b0[23:16] | a2b0[15:8] | a3b3[7:0]
        # 1 0 1  | a0b0[31:24] | a1b1[23:16] | a2b1[15:8] | a3b3[7:0]
        # 1 1 0  | a0b0[31:24] | a1b0[23:16] | a2b2[15:8] | a3b3[7:0]
        # 1 1 1  | a0b0[31:24] | a1b1[23:16] | a2b2[15:8] | a3b3[7:0]

        # Each output for o3 is given by a3bx and the partial results
        # for o2 (namely, a2bx, a1bx, and a0b0). If I calculate the
        # partial results [a0b0, a1bx, a2bx, a3bx], I can use just
        # those partial results to calculate a0, a1, a2, and a3
        partial_results = []
        partial_results.append(a_intervals[0] << b_intervals[0])
        for i in range(1, len(out_intervals)):
            s, e = intervals[i]

            # This calculates which partition of b to select the
            # shifter from. According to the table above, the
            # partition to select is given by the highest set bit in
            # the partition mask, this calculates that with a mux
            # chain
            element = b_intervals[0]
            for index in range(i):
                element = Mux(gates[index], b_intervals[index+1], element)

            # This computes the partial results table
            shifter = Signal(8)
            comb += shifter.eq(element)
            partial = Signal(width, name="partial%d" % i)
            comb += partial.eq(a_intervals[i] << shifter)

            partial_results.append(partial)

        out = []

        # This calculates the outputs o0-o3 from the partial results
        # table above.
        for i in range(len(out_intervals)):
            result = 0
            for j in range(i):
                s,e = intervals[i-j]
                result = Mux(gates[j], 0, result | partial_results[j][s:e])
            result = partial_results[i] | result
            s,e = intervals[0]
            out.append(result[s:e])

        comb += self.output.eq(Cat(*out))


        return m

