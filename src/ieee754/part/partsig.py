"""
Copyright (C) 2020 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

dynamic-partitionable class similar to Signal, which, when the partition
is fully open will be identical to Signal.  when partitions are closed,
the class turns into a SIMD variant of Signal.  *this is dynamic*.

http://bugs.libre-riscv.org/show_bug.cgi?id=132
"""

from nmigen import (Module, Signal, Elaboratable,
                    )
from ieee754.part_mul_add.adder import PartitionedAdder

class PartitionedSignal(Elaboratable):
    def __init__(self, partition_points, *args, **kwargs)
                 reset=0, reset_less=False,
                 attrs=None, decoder=None, src_loc_at=0):
        self.partpoints = partition_points
        self.sig = Signal(*args, **kwargs)
        self.modnames = {}
        for name in ['add']:
            self.modnames[name] = 0

    def elaboratable(self, platform):
        self.m = m = Module()
        return m

    def get_modname(self, category):
        self.modnames[category] += 1
        return "%s%d" % (category, self.modnames[category])

    def __xor__(self, other):
        if isinstance(other, PartitionedSignal):
            return self.sig ^ other.sig
        return self.sig ^ other

    def __add__(self, other):
        shape = self.sig.shape()
        pa = PartitionedAdder(shape[0], self.partpoints)
        setattr(self.m.submodules, self.get_modname('add'), pa)
        comb = self.m.d.comb
        comb += pa.a.eq(self.sig)
        if isinstance(other, PartitionedSignal):
            comb += pa.b.eq(other.sig)
        else:
            comb += pa.b.eq(other)
        return pa.output
