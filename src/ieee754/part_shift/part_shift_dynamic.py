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

        # create a matrix of partial shift-results (similar to PartitionedMul
        # matrices).  These however have to be of length suitable to contain
        # the full shifted "contribution".  i.e. B from the LSB *could* contain
        # a number great enough to shift the entirety of A LSB right up to
        # the MSB of the output, however B from the *MSB* is *only* going
        # to contribute to the *MSB* of the output.
        for i in range(len(keys)):
            row = []
            start = 0
            for j in range(len(keys)):
                end = keys[j]
                row.append(Signal(width - start,
                           name="matrix[%d][%d]" % (i, j)))
                start = end
            matrix.append(row)

        # break out both the input and output into partition-stratified blocks
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

        # actually calculate the shift-partials here
        for i, b in enumerate(b_intervals):
            start = 0
            for j in range(i, len(a_intervals)):
                a = a_intervals[j]
                end = keys[i]
                result_width = matrix[i][j].width
                rw = math.ceil(math.log2(result_width + 1))
                # XXX!
                bw = math.ceil(math.log2(self.output.width + 1))
                tshift = Signal(bw, name="ts%d_%d" % (i, j), reset_less=True)
                ow = math.ceil(math.log2(width-start))
                maxshift = (1<<(ow))
                print ("part", i, b, j, a, rw, bw, ow, maxshift)
                with m.If(b[:bw] < maxshift):
                    comb += tshift.eq(b[:bw])
                with m.Else():
                    comb += tshift.eq(maxshift)
                comb += matrix[i][j].eq(a << tshift)
                start = end

        # now create a switch statement which sums the relevant partial results
        # in each output-partition

        out = []
        intermed = matrix[0][0]
        s, e = intervals[0]
        out.append(intermed[s:e])
        for i in range(1, len(out_intervals)):
            s, e = intervals[i]
            index = gates[:i]  # selects the 'i' least significant bits
                               # of gates
            element = matrix[0][i]
            for index in range(i):
                element = Mux(gates[index], matrix[index+1][i], element)
            print(keys[i-1])
            temp = Signal(matrix[0][i].width, name="intermed%d" % i)
            print(intermed[keys[0]:])
            # XXX bit of a mess here, but rather than select
            # element or (element | intermed), select between 0 or intermed
            # then unconditionally "|" element on top (once copied into
            # a named Signal)
            # XXX TODO: hmmm rather than pass down the actual intermed
            # here, why not accumulate a cascade of "do we need to include
            # this partial result" things, *then* OR them together?
            # this is where it sort-of becomes like the gt_combiner
            intermed = Mux(gates[i-1], 0, intermed[keys[0]:])
            intermed2 = Signal(intermed.shape())
            comb += intermed2.eq(intermed | element)
            intermed = intermed2
            comb += temp.eq(intermed)
            out.append(temp[:e-s])

        comb += self.output.eq(Cat(*out))

        return m

