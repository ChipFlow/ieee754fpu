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
from ieee754.part_shift.bitrev import GatedBitReverse
import math


class PartitionedScalarShift(Elaboratable):
    def __init__(self, width, partition_points):
        self.width = width
        self.partition_points = PartitionPoints(partition_points)

        self.data = Signal(width, reset_less=True)
        self.shiftbits = math.ceil(math.log2(width))
        self.shifter = Signal(self.shiftbits, reset_less=True)
        self.output = Signal(width, reset_less=True)
        self.bitrev = Signal(reset_less=True) # Whether to bit-reverse the
                                              # input and output

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        width = self.width
        pwid = self.partition_points.get_max_partition_count(width)-1
        shiftbits = self.shiftbits
        gates = self.partition_points.as_sig()

        parts = []
        outputs = []
        shiftparts = []
        intervals = []
        keys = list(self.partition_points.keys()) + [self.width]

        m.submodules.in_br = in_br = GatedBitReverse(self.data.width)
        comb += in_br.data.eq(self.data)
        comb += in_br.reverse_en.eq(self.bitrev)

        m.submodules.out_br = out_br = GatedBitReverse(self.data.width)
        comb += out_br.reverse_en.eq(self.bitrev)
        comb += self.output.eq(out_br.output)

        m.submodules.gate_br = gate_br = GatedBitReverse(pwid)
        comb += gate_br.data.eq(gates)
        comb += gate_br.reverse_en.eq(self.bitrev)
        start = 0
        for i in range(len(keys)):
            end = keys[i]
            parts.append(in_br.output[start:end])
            outputs.append(out_br.data[start:end])
            intervals.append((start,end))
            start = end  # for next time round loop

        min_bits = math.ceil(math.log2(intervals[0][1] - intervals[0][0]))
        shifter_masks = []
        for i in range(len(intervals)):
            max_bits = math.ceil(math.log2(width-intervals[i][0]))
            sm_mask = Signal(shiftbits, name="sm_mask%d" % i, reset_less=True)
            if pwid-i != 0:
                sm = ShifterMask(pwid-i, shiftbits,
                                 max_bits, min_bits)
                comb += sm.gates.eq(gate_br.output[i:pwid])
                comb += sm_mask.eq(sm.mask)
                setattr(m.submodules, "sm%d" % i, sm)
            else: # having a 0 width signal seems to give the proof issues
                # this seems to fix it
                comb += sm_mask.eq((1<<min_bits)-1)
            if i != 0:
                shifter_mask = Signal(shiftbits, name="shifter_mask%d" % i,
                                      reset_less=True)
                comb += shifter_mask.eq(Mux(gate_br.output[i-1],
                                         sm_mask,
                                         shifter_masks[i-1]))
                shifter_masks.append(shifter_mask)
            else:
                shifter_masks.append(sm_mask)

        for i, interval in enumerate(intervals):
            s,e = interval
            sp = Signal(width, name="sp%d" % i, reset_less=True)
            _shifter = Signal(self.shifter.width, name="shifter%d" % i,
                              reset_less=True)
            comb += _shifter.eq(self.shifter & shifter_masks[i])
            comb += sp[s:].eq(in_br.output[s:e] << _shifter)
            shiftparts.append(sp)


        for i, interval in enumerate(intervals):
            start, end = interval
            if i == 0:
                intermed = shiftparts[i]
            else:
                intermed = shiftparts[i] | Mux(gate_br.output[i-1], 0, prev)
            comb += outputs[i].eq(intermed[start:end])
            prev = intermed

        return m
