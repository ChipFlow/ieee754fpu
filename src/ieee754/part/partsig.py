"""
Copyright (C) 2020 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

dynamic-partitionable class similar to Signal, which, when the partition
is fully open will be identical to Signal.  when partitions are closed,
the class turns into a SIMD variant of Signal.  *this is dynamic*.

http://bugs.libre-riscv.org/show_bug.cgi?id=132
"""

from nmigen import (Module, Signal, Elaboratable,
                    )

class PartitionedSignal(Elaboratable):
    def __init__(self, partition_points, *args, **kwargs)
                 reset=0, reset_less=False,
                 attrs=None, decoder=None, src_loc_at=0):
        self.partpoints = partition_points
        self.sig = Signal(*args, **kwargs)

    def elaboratable(self, platform):
        self.m = m = Module()
        return m

    
