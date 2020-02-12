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

        # actually calculate the shift-partials here
        for i, b in enumerate(b_intervals):
            start = 0
            for j, a in enumerate(a_intervals):
                end = keys[i]
                result_width = matrix[i][j].width
                bwidth = math.ceil(math.log2(result_width + 1))
                comb += matrix[i][j].eq(a << b[:bwidth])
                start = end

        # now create a switch statement which sums the relevant partial results
        # in each output-partition

        intermed = matrix[0][0]
        comb += out_intervals[0].eq(intermed)
        for i in range(1, len(out_intervals)):
            index = gates[:i]  # selects the 'i' least significant bits
                               # of gates
            element = Signal(width, name="element%d" % i)
            for index in range(1<<i):
                print(index)
                with m.Switch(gates[:i]):
                    with m.Case(index):
                        index = math.ceil(math.log2(index + 1))
                        comb += element.eq(matrix[index][i])
            print(keys[i-1])
            temp = Signal(width, name="intermed%d" % i)
            print(intermed[keys[0]:])
            intermed = Mux(gates[i-1], element, element | intermed[keys[0]:])
            comb += temp.eq(intermed)
            comb += out_intervals[i].eq(intermed)


        return m

