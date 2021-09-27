# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

"""
Copyright (C) 2020 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

dynamically-partitionable "comparison" class, directly equivalent
to Signal.__eq__ except SIMD-partitionable

See:

* http://libre-riscv.org/3d_gpu/architecture/dynamic_simd/mux
* http://bugs.libre-riscv.org/show_bug.cgi?id=132
"""

from nmigen import Signal, Module, Elaboratable, Mux
from ieee754.part_mul_add.partpoints import PartitionPoints
from ieee754.part_mul_add.partpoints import make_partition


modcount = 0 # global for now
def PMux(m, mask, sel, a, b):
    global modcount
    modcount += 1
    width = len(a.sig)  # get width
    part_pts = make_partition(mask, width) # create partition points
    pm = PartitionedMux(width, part_pts)
    m.d.comb += pm.a.eq(a.sig)
    m.d.comb += pm.b.eq(b.sig)
    m.d.comb += pm.sel.eq(sel)
    setattr(m.submodules, "pmux%d" % modcount, pm)
    return pm.output


class PartitionedMux(Elaboratable):
    """PartitionedMux: Partitioned "Mux"

    takes a partition point set, subdivides a and b into blocks
    and "selects" them.  the assumption is that "sel" has had
    its LSB propagated up throughout the entire partition, and
    consequently the incoming selector (sel) can completely
    ignore what the *actual* partition bits are.
    """
    def __init__(self, width, partition_points):
        self.width = width
        self.partition_points = PartitionPoints(partition_points)
        self.mwidth = len(self.partition_points)+1
        self.a = Signal(width, reset_less=True)
        self.b = Signal(width, reset_less=True)
        self.sel = Signal(self.mwidth, reset_less=True)
        self.output = Signal(width, reset_less=True)
        assert self.partition_points.fits_in_width(width), \
                    "partition_points doesn't fit in width"

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        # loop across all partition ranges.
        # drop the selection directly into the output.
        keys = list(self.partition_points.keys()) + [self.width]
        stt = 0
        for i in range(len(keys)):
            end = keys[i]
            mux = self.output[stt:end]
            comb += mux.eq(Mux(self.sel[i], self.a[stt:end], self.b[stt:end]))
            stt = end  # for next time round loop

        return m

    def ports(self):
        return [self.a.sig, self.b.sig, self.sel, self.output]

