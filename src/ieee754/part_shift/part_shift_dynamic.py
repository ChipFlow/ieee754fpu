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
        intervals = []
        widths = []
        start = 0
        for i in range(len(keys)):
            end = keys[i]
            widths.append(width - start)
            a_intervals.append(self.a[start:end])
            b_intervals.append(self.b[start:end])
            intervals.append([start,end])
            start = end

        min_bits = math.ceil(math.log2(intervals[0][1] - intervals[0][0]))
        max_bits = math.ceil(math.log2(width))

        # shifts are normally done as (e.g. for 32 bit) result = a & (b&0b11111)
        # truncating the b input.  however here of course the size of the
        # partition varies dynamically.
        shifter_masks = []
        for i in range(len(b_intervals)):
            mask = Signal(b_intervals[i].shape(), name="shift_mask%d" % i)
            bits = []
            for j in range(i, gates.width):
                if bits:
                    bits.append(~gates[j] & bits[-1])
                else:
                    bits.append(~gates[j])
            comb += mask.eq(Cat((1 << min_bits)-1, bits)
                            & ((1 << max_bits)-1))
            shifter_masks.append(mask)

        print(shifter_masks)

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
        shiftbits = math.ceil(math.log2(width))
        element = b_intervals[0] & shifter_masks[0]
        partial_results = []
        partial_results.append(a_intervals[0] << element)
        for i in range(1, len(keys)):
            s, e = intervals[i]
            masked = Signal(b_intervals[i].shape(), name="masked%d" % i)
            comb += masked.eq(b_intervals[i] & shifter_masks[i])
            element = Mux(gates[i-1], masked, element)

            # This calculates which partition of b to select the
            # shifter from. According to the table above, the
            # partition to select is given by the highest set bit in
            # the partition mask, this calculates that with a mux
            # chain

            # This computes the partial results table
            shifter = Signal(shiftbits, name="shifter%d" % i)
            comb += shifter.eq(element)
            partial = Signal(width, name="partial%d" % i)
            comb += partial.eq(a_intervals[i] << shifter)

            partial_results.append(partial)

        out = []

        # This calculates the outputs o0-o3 from the partial results
        # table above.
        s,e = intervals[0]
        result = partial_results[0]
        out.append(result[s:e])
        for i in range(1, len(keys)):
            start, end = (intervals[i][0], width)
            result = partial_results[i] | \
                Mux(gates[i-1], 0, result[intervals[0][1]:])[:end-start]
            print("select: [%d:%d]" % (start, end))
            res = Signal(width, name="res%d" % i)
            comb += res.eq(result)
            s,e = intervals[0]
            out.append(res[s:e])

        comb += self.output.eq(Cat(*out))

        return m

