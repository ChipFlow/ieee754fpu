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

class ShifterMask(Elaboratable):
    def __init__(self, pwid, bwid, max_bits, min_bits):
        self.max_bits = max_bits
        self.min_bits = min_bits
        self.pwid = pwid
        self.mask = Signal(bwid, reset_less=True)
        self.gates = Signal(pwid, reset_less=True)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        # zero-width mustn't try to do anything
        if self.pwid == 0:
            self.mask.eq((1<<self.min_bits)-1)
            return m

        bits = Signal(self.pwid, reset_less=True)
        bl = []
        for j in range(self.pwid):
            if j != 0:
                bl.append((~self.gates[j]) & bits[j-1])
            else:
                bl.append(~self.gates[j])
        # XXX ARGH, really annoying: simulation bug, can't use Cat(*bl).
        for j in range(bits.shape()[0]):
            comb += bits[j].eq(bl[j])
        comb += self.mask.eq(Cat((1 << self.min_bits)-1, bits)
                        & ((1 << self.max_bits)-1))

        return m


class PartialResult(Elaboratable):
    def __init__(self, pwid, bwid, reswid):
        self.pwid = pwid
        self.bwid = bwid
        self.reswid = reswid
        self.element = Signal(bwid, reset_less=True)
        self.elmux = Signal(bwid, reset_less=True)
        self.a_interval = Signal(bwid, reset_less=True)
        self.masked = Signal(bwid, reset_less=True)
        self.gate = Signal(reset_less=True)
        self.partial = Signal(reswid, reset_less=True)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        shiftbits = math.ceil(math.log2(self.reswid+1))+1 # hmmm...
        print ("partial", self.reswid, self.pwid, shiftbits)
        element = Mux(self.gate, self.masked, self.element)
        comb += self.elmux.eq(element)
        element = self.elmux

        # This calculates which partition of b to select the
        # shifter from. According to the table above, the
        # partition to select is given by the highest set bit in
        # the partition mask, this calculates that with a mux
        # chain

        # This computes the partial results table.  note that
        # the shift amount is truncated because there's no point
        # trying to shift data by 64 bits if the result width
        # is only 8.
        shifter = Signal(shiftbits, reset_less=True)
        maxval = C(self.reswid, element.shape())
        with m.If(element > maxval):
            comb += shifter.eq(maxval)
        with m.Else():
            comb += shifter.eq(element)
        comb += self.partial.eq(self.a_interval << shifter)

        return m


class PartitionedDynamicShift(Elaboratable):
    def __init__(self, width, partition_points):
        self.width = width
        self.partition_points = PartitionPoints(partition_points)

        self.a = Signal(width, reset_less=True)
        self.b = Signal(width, reset_less=True)
        self.output = Signal(width, reset_less=True)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        width = self.width
        pwid = self.partition_points.get_max_partition_count(width)-1
        gates = Signal(pwid, reset_less=True)
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

        # shifts are normally done as (e.g. for 32 bit) result = a & (b&0b11111)
        # truncating the b input.  however here of course the size of the
        # partition varies dynamically.
        shifter_masks = []
        for i in range(len(b_intervals)):
            max_bits = math.ceil(math.log2(width-intervals[i][0]))
            sm = ShifterMask(pwid-i, b_intervals[i].shape()[0],
                             max_bits, min_bits)
            setattr(m.submodules, "sm%d" % i, sm)
            comb += sm.gates.eq(gates[i:pwid])
            shifter_masks.append(sm.mask)

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
        element = Signal(b_intervals[0].shape(), reset_less=True)
        comb += element.eq(b_intervals[0] & shifter_masks[0])
        partial_results = []
        partial = Signal(width, name="partial0", reset_less=True)
        comb += partial.eq(a_intervals[0] << element)
        partial_results.append(partial)
        for i in range(1, len(keys)):
            reswid = width - intervals[i][0]
            shiftbits = math.ceil(math.log2(reswid+1))+1 # hmmm...
            print ("partial", reswid, width, intervals[i], shiftbits)
            s, e = intervals[i]
            pr = PartialResult(pwid, b_intervals[i].shape()[0], reswid)
            setattr(m.submodules, "pr%d" % i, pr)
            masked = Signal(b_intervals[i].shape(), name="masked%d" % i,
                          reset_less=True)
            comb += pr.masked.eq(b_intervals[i] & shifter_masks[i])
            comb += pr.gate.eq(gates[i-1])
            comb += pr.element.eq(element)
            comb += pr.a_interval.eq(a_intervals[i])
            partial_results.append(pr.partial)
            element = pr.elmux

        out = []

        # This calculates the outputs o0-o3 from the partial results
        # table above.  Note: only relevant bits of the partial result equal
        # to the width of the output column are accumulated in a Mux-cascade.
        s,e = intervals[0]
        result = partial_results[0]
        out.append(result[s:e])
        for i in range(1, len(keys)):
            start, end = (intervals[i][0], width)
            reswid = width - start
            sel = Mux(gates[i-1], 0, result[intervals[0][1]:][:end-start])
            print("select: [%d:%d]" % (start, end))
            res = Signal(end-start+1, name="res%d" % i, reset_less=True)
            comb += res.eq(partial_results[i] | sel)
            result = res
            s,e = intervals[0]
            out.append(res[s:e])

        comb += self.output.eq(Cat(*out))

        return m

