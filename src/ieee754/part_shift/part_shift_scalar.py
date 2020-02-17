# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

"""
Copyright (C) 2020 Michael Nolan <mtnolan2640@gmail.com>

dynamically partitionable shifter. Only the operand to be shifted can
be partitioned, the amount to shift by *must* be a scalar

See:

* http://libre-riscv.org/3d_gpu/architecture/dynamic_simd/shift/
* http://bugs.libre-riscv.org/show_bug.cgi?id=173
"""
from nmigen import Signal, Module, Elaboratable, Cat, Mux
from ieee754.part_mul_add.partpoints import PartitionPoints
from ieee754.part_shift.part_shift_dynamic import ShifterMask
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
        pwid = self.partition_points.get_max_partition_count(width)-1
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
            start = end  # for next time round loop

        min_bits = math.ceil(math.log2(intervals[0][1] - intervals[0][0]))
        shifter_masks = []
        for i in range(len(intervals)):
            max_bits = math.ceil(math.log2(width-intervals[i][0]))
            sm_mask = Signal(shiftbits, name="sm_mask%d" % i)
            if pwid-i != 0:
                sm = ShifterMask(pwid-i, shiftbits,
                                 max_bits, min_bits)
                comb += sm.gates.eq(gates[i:pwid])
                comb += sm_mask.eq(sm.mask)
                setattr(m.submodules, "sm%d" % i, sm)
            else: # having a 0 width signal seems to give the proof issues
                # this seems to fix it
                comb += sm_mask.eq((1<<min_bits)-1)
            if i != 0:
                shifter_mask = Signal(shiftbits, name="shifter_mask%d" % i)
                comb += shifter_mask.eq(Mux(gates[i-1],
                                         sm_mask,
                                         shifter_masks[i-1]))
                shifter_masks.append(shifter_mask)
            else:
                shifter_masks.append(sm_mask)

        for i, interval in enumerate(intervals):
            s,e = interval
            sp = Signal(width, name="sp%d" % i)
            _shifter = Signal(self.shifter.width, name="shifter%d" % i)
            comb += _shifter.eq(self.shifter & shifter_masks[i])
            comb += sp[s:].eq(self.data[s:e] << _shifter)
            shiftparts.append(sp)


        for i, interval in enumerate(intervals):
            start, end = interval
            if i == 0:
                intermed = shiftparts[i]
            else:
                intermed = shiftparts[i] | Mux(gates[i-1], 0, prev)
            comb += outputs[i].eq(intermed[start:end])
            prev = intermed

        return m
