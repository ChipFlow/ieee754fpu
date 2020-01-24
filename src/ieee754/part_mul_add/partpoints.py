# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information
"""Integer Multiplication."""

from nmigen import Signal, Value, Cat, C

def make_partition(mask, width):
    """ from a mask and a bitwidth, create partition points.
        note that the assumption is that the mask indicates the
        breakpoints in regular intervals, and that the last bit (MSB)
        of the mask is therefore *ignored*.
        mask len = 4, width == 16 will return:
            {4: mask[0], 8: mask[1], 12: mask[2]}
        mask len = 8, width == 64 will return:
            {8: mask[0], 16: mask[1], 24: mask[2], .... 56: mask[6]}
    """
    ppoints = {}
    mlen = mask.shape()[0]
    ppos = mlen
    midx = 0
    while ppos < width:
        ppoints[ppos] = mask[midx]
        ppos += mlen
        midx += 1
    return ppoints


class PartitionPoints(dict):
    """Partition points and corresponding ``Value``s.

    The points at where an ALU is partitioned along with ``Value``s that
    specify if the corresponding partition points are enabled.

    For example: ``{1: True, 5: True, 10: True}`` with
    ``width == 16`` specifies that the ALU is split into 4 sections:
    * bits 0 <= ``i`` < 1
    * bits 1 <= ``i`` < 5
    * bits 5 <= ``i`` < 10
    * bits 10 <= ``i`` < 16

    If the partition_points were instead ``{1: True, 5: a, 10: True}``
    where ``a`` is a 1-bit ``Signal``:
    * If ``a`` is asserted:
        * bits 0 <= ``i`` < 1
        * bits 1 <= ``i`` < 5
        * bits 5 <= ``i`` < 10
        * bits 10 <= ``i`` < 16
    * Otherwise
        * bits 0 <= ``i`` < 1
        * bits 1 <= ``i`` < 10
        * bits 10 <= ``i`` < 16
    """

    def __init__(self, partition_points=None):
        """Create a new ``PartitionPoints``.

        :param partition_points: the input partition points to values mapping.
        """
        super().__init__()
        if partition_points is not None:
            for point, enabled in partition_points.items():
                if not isinstance(point, int):
                    raise TypeError("point must be a non-negative integer")
                if point < 0:
                    raise ValueError("point must be a non-negative integer")
                self[point] = Value.cast(enabled)

    def like(self, name=None, src_loc_at=0, mul=1):
        """Create a new ``PartitionPoints`` with ``Signal``s for all values.

        :param name: the base name for the new ``Signal``s.
        :param mul: a multiplication factor on the indices
        """
        if name is None:
            name = Signal(src_loc_at=1+src_loc_at).name  # get variable name
        retval = PartitionPoints()
        for point, enabled in self.items():
            point *= mul
            retval[point] = Signal(enabled.shape(), name=f"{name}_{point}")
        return retval

    def eq(self, rhs):
        """Assign ``PartitionPoints`` using ``Signal.eq``."""
        if set(self.keys()) != set(rhs.keys()):
            raise ValueError("incompatible point set")
        for point, enabled in self.items():
            yield enabled.eq(rhs[point])

    def as_mask(self, width, mul=1):
        """Create a bit-mask from `self`.

        Each bit in the returned mask is clear only if the partition point at
        the same bit-index is enabled.

        :param width: the bit width of the resulting mask
        :param mul: a "multiplier" which in-place expands the partition points
                    typically set to "2" when used for multipliers
        """
        bits = []
        for i in range(width):
            i /= mul
            if i.is_integer() and int(i) in self:
                bits.append(~self[i])
            else:
                bits.append(True)
        return Cat(*bits)

    def get_max_partition_count(self, width):
        """Get the maximum number of partitions.

        Gets the number of partitions when all partition points are enabled.
        """
        retval = 1
        for point in self.keys():
            if point < width:
                retval += 1
        return retval

    def fits_in_width(self, width):
        """Check if all partition points are smaller than `width`."""
        for point in self.keys():
            if point >= width:
                return False
        return True

    def part_byte(self, index, mfactor=1): # mfactor used for "expanding"
        if index == -1 or index == 7:
            return C(True, 1)
        assert index >= 0 and index < 8
        return self[(index * 8 + 8)*mfactor]


