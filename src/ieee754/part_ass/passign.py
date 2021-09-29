# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

"""
Copyright (C) 2021 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

dynamically-partitionable "assign" class, directly equivalent
to nmigen Assign

See:

* http://libre-riscv.org/3d_gpu/architecture/dynamic_simd/assign
* http://bugs.libre-riscv.org/show_bug.cgi?id=709

"""



modcount = 0 # global for now
def PAssign(m, shape, assign, mask):
    from ieee754.part_ass.assign import PartitionedAssign # recursion issue
    global modcount
    modcount += 1
    pc = PartitionedAssign(shape, assign, mask)
    setattr(m.submodules, "pass%d" % modcount, pc)
    return pc.output


