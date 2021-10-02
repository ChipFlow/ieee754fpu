# SPDX-License-Identifier: LGPL-3-or-later
# See Notices.txt for copyright information

from typing import Set, Tuple
from nmigen.hdl.ast import AnyConst, Assert, Assume, Signal
from nmigen.hdl.dsl import Module
from ieee754.partitioned_signal_tester import (
    PartitionedSignalTester, Layout, Lane, formal)
import unittest


class TestFormal(unittest.TestCase):
    def test_formal(self):
        m = Module()
        a = Signal(10)
        b = Signal(10)
        m.d.comb += a.eq(AnyConst(10))
        m.d.comb += b.eq(AnyConst(10))
        m.d.comb += Assume(a * b == 1021 * 1019)
        m.d.comb += Assert((a == 1021) | (a == 1019))
        formal(self, m)

    @unittest.expectedFailure
    def test_formal_fail(self):
        m = Module()
        a = Signal(10)
        b = Signal(10)
        m.d.comb += a.eq(AnyConst(10))
        m.d.comb += b.eq(AnyConst(10))
        m.d.comb += Assume(a * b == 1021 * 1019)
        m.d.comb += Assert(a == 1021)
        formal(self, m)


class TestLayout(unittest.TestCase):
    maxDiff = None

    def test_repr(self):
        self.assertEqual(repr(Layout({3: False, 7: True}, 16)),
                         "Layout((0, 3, 7, 16), width=16)")
        self.assertEqual(repr(Layout({7: False, 3: True}, 16)),
                         "Layout((0, 3, 7, 16), width=16)")
        self.assertEqual(repr(Layout(range(0, 10, 2), 10)),
                         "Layout((0, 2, 4, 6, 8, 10), width=10)")
        self.assertEqual(repr(Layout(range(0, 10, 2))),
                         "Layout((0, 2, 4, 6, 8), width=8)")
        self.assertEqual(repr(Layout(())),
                         "Layout((0,), width=0)")
        self.assertEqual(repr(Layout((1,))),
                         "Layout((0, 1), width=1)")

    def test_cast(self):
        a = Layout.cast((1, 2, 3))
        self.assertEqual(repr(a),
                         "Layout((0, 1, 2, 3), width=3)")
        b = Layout.cast(a)
        self.assertIs(a, b)

    def test_part_signal_count(self):
        a = Layout.cast(())
        b = Layout.cast((1,))
        c = Layout.cast((1, 3))
        d = Layout.cast((0, 1, 3))
        e = Layout.cast((1, 2, 3))
        self.assertEqual(a.part_signal_count, 0)
        self.assertEqual(b.part_signal_count, 0)
        self.assertEqual(c.part_signal_count, 1)
        self.assertEqual(d.part_signal_count, 1)
        self.assertEqual(e.part_signal_count, 2)

    def test_lanes(self):
        a = Layout.cast(())
        self.assertEqual(list(a.lanes()), [])
        b = Layout.cast((1,))
        self.assertEqual(list(b.lanes()), [Lane(0, 1, b)])
        c = Layout.cast((1, 3))
        self.assertEqual(list(c.lanes()),
                         [Lane(0, 1, c),
                          Lane(1, 2, c),
                          Lane(0, 3, c)])
        d = Layout.cast((1, 4, 5))
        self.assertEqual(list(d.lanes()),
                         [Lane(0, 1, d),
                          Lane(4, 1, d),
                          Lane(1, 3, d),
                          Lane(0, 4, d),
                          Lane(1, 4, d),
                          Lane(0, 5, d)])
        e = Layout(range(0, 32, 8), 32)
        self.assertEqual(list(e.lanes()),
                         [Lane(0, 8, e),
                          Lane(8, 8, e),
                          Lane(16, 8, e),
                          Lane(24, 8, e),
                          Lane(0, 16, e),
                          Lane(8, 16, e),
                          Lane(16, 16, e),
                          Lane(0, 24, e),
                          Lane(8, 24, e),
                          Lane(0, 32, e)])

    def test_is_compatible(self):
        a = Layout.cast(())
        b = Layout.cast((1,))
        c = Layout.cast((1, 2))
        d = Layout.cast((4, 5))
        e = Layout.cast((1, 2, 3, 4))
        f = Layout.cast((8, 16, 24, 32))
        compatibility_classes = {
            a: 0,
            b: 1,
            c: 2,
            d: 2,
            e: 4,
            f: 4,
        }
        for lhs in compatibility_classes:
            for rhs in compatibility_classes:
                with self.subTest(lhs=lhs, rhs=rhs):
                    self.assertEqual(compatibility_classes[lhs]
                                     == compatibility_classes[rhs],
                                     lhs.is_compatible(rhs))

    def test_translate_lanes_to(self):
        src = Layout((0, 3, 7, 12, 13))
        dest = Layout((0, 8, 16, 24, 32))
        src_lanes = list(src.lanes())
        src_lanes.sort(key=lambda lane: lane.start)
        dest_lanes = list(dest.lanes())
        dest_lanes.sort(key=lambda lane: lane.start)
        self.assertEqual(len(src_lanes), len(dest_lanes))
        for src_lane, dest_lane in zip(src_lanes, dest_lanes):
            with self.subTest(src_lane=src_lane, dest_lane=dest_lane):
                self.assertEqual(src_lane.translate_to(dest), dest_lane)
                self.assertEqual(dest_lane.translate_to(src), src_lane)


class TestLane(unittest.TestCase):
    def test_is_active(self):
        layout = Layout((0, 8, 16, 24, 32))
        def do_test(part_starts: Tuple[bool, ...],
                    expected_lanes: Set[Tuple[int, int]]):
            with self.subTest(part_starts=part_starts,
                              expected_lanes=expected_lanes):
                for lane in layout.lanes():
                    expected = (lane.start, lane.size) in expected_lanes
                    with self.subTest(lane=lane):
                        self.assertEqual(lane.is_active(part_starts),
                                         expected)

        _0 = False
        _1 = True
        do_test((_1, _0, _0, _0, _1),
                {(0, 32)})
        do_test((_1, _0, _0, _1, _1),
                {(0, 24), (24, 8)})
        do_test((_1, _0, _1, _0, _1),
                {(0, 16), (16, 16)})
        do_test((_1, _0, _1, _1, _1),
                {(0, 16), (16, 8), (24, 8)})
        do_test((_1, _1, _0, _0, _1),
                {(0, 8), (8, 24)})
        do_test((_1, _1, _0, _1, _1),
                {(0, 8), (8, 16), (24, 8)})
        do_test((_1, _1, _1, _0, _1),
                {(0, 8), (8, 8), (16, 16)})
        do_test((_1, _1, _1, _1, _1),
                {(0, 8), (8, 8), (16, 8), (24, 8)})

    def test_as_slice(self):
        slice_target = tuple(range(8))
        layout = Layout((0, 2, 4, 6, 8))
        slices = list(slice_target[lane.as_slice()]
                      for lane in layout.lanes())
        self.assertEqual(slices,
                         [(0, 1),
                          (2, 3),
                          (4, 5),
                          (6, 7),
                          (0, 1, 2, 3),
                          (2, 3, 4, 5),
                          (4, 5, 6, 7),
                          (0, 1, 2, 3, 4, 5),
                          (2, 3, 4, 5, 6, 7),
                          (0, 1, 2, 3, 4, 5, 6, 7)])


class TestPartitionedSignalTester(unittest.TestCase):
    def test_sim_identity(self):
        m = Module()
        PartitionedSignalTester(m,
                                lambda inputs: inputs[0],
                                lambda lane, inputs: inputs[0],
                                (0, 8, 16, 24, 32)).run_sim(self)

    def test_formal_identity(self):
        m = Module()
        PartitionedSignalTester(m,
                                lambda inputs: inputs[0],
                                lambda lane, inputs: inputs[0],
                                (0, 8, 16, 24, 32)).run_formal(self)

    def test_sim_pass_through_input(self):
        for which_input in range(0, 2):
            m = Module()
            PartitionedSignalTester(m,
                                    lambda inputs: inputs[which_input],
                                    lambda lane, inputs: inputs[which_input],
                                    (0, 8, 16, 24, 32),
                                    (0, 1, 2, 3, 4)).run_sim(self)

    def test_formal_pass_through_input(self):
        for which_input in range(0, 2):
            m = Module()
            PartitionedSignalTester(m,
                                    lambda inputs: inputs[which_input],
                                    lambda lane, inputs: inputs[which_input],
                                    (0, 8, 16, 24, 32),
                                    (0, 1, 2, 3, 4)).run_formal(self)


if __name__ == '__main__':
    unittest.main()
