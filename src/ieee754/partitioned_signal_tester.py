# SPDX-License-Identifier: LGPL-3-or-later
# See Notices.txt for copyright information
from enum import Enum
import shutil
from nmigen.hdl.ast import (AnyConst, Assert, Signal, Value, ValueCastable)
from nmigen.hdl.dsl import Module
from nmigen.hdl.ir import Elaboratable, Fragment
from nmigen.sim import Simulator, Delay
from ieee754.part.partsig import PartitionedSignal, PartitionPoints
import unittest
import textwrap
import subprocess
from hashlib import sha256
from nmigen.back import rtlil
from nmutil.get_test_path import get_test_path, _StrPath


def formal(test_case, hdl, *, base_path="formal_test_temp"):
    hdl = Fragment.get(hdl, platform="formal")
    path = get_test_path(test_case, base_path)
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True)
    sby_name = "config.sby"
    sby_file = path / sby_name

    sby_file.write_text(textwrap.dedent(f"""\
    [options]
    mode prove
    depth 1
    wait on

    [engines]
    smtbmc

    [script]
    read_rtlil top.il
    prep

    [file top.il]
    {rtlil.convert(hdl)}
    """), encoding="utf-8")
    sby = shutil.which('sby')
    assert sby is not None
    with subprocess.Popen(
        [sby, sby_name],
        cwd=path, text=True, encoding="utf-8",
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE
    ) as p:
        stdout, stderr = p.communicate()
        if p.returncode != 0:
            test_case.fail(f"Formal failed:\n{stdout}")


@final
class Layout:
    __lane_starts_for_sizes
    """keys are in sorted order"""

    part_indexes
    """bit indexes of partition points in sorted order, always includes
    `0` and `self.width`"""

    @staticmethod
    def cast(layout, width=None):
        if isinstance(layout, Layout):
            return layout
        return Layout(layout, width)

    def __init__(self, part_indexes, width=None):
        part_indexes = set(part_indexes)
        for p in part_indexes:
            assert isinstance(p, int)
            assert 0 <= p
        if width is not None:
            width = Layout.get_width(width)
            for p in part_indexes:
                assert p <= width
            part_indexes.add(width)
        part_indexes.add(0)
        part_indexes = list(part_indexes)
        part_indexes.sort()
        self.part_indexes = tuple(part_indexes)
        sizes: List[int] = []
        for start_index in range(len(self.part_indexes)):
            start = self.part_indexes[start_index]
            for end in self.part_indexes[start_index + 1:]:
                sizes.append(end - start)
        sizes.sort()
        # build in sorted order
        self.__lane_starts_for_sizes = {size: {} for size in sizes}
        for start_index in range(len(self.part_indexes)):
            start = self.part_indexes[start_index]
            for end in self.part_indexes[start_index + 1:]:
                self.__lane_starts_for_sizes[end - start][start] = None

    @property
    def width(self):
        return self.part_indexes[-1]

    @property
    def part_signal_count(self):
        return max(len(self.part_indexes) - 2, 0)

    @staticmethod
    def get_width(width):
        if isinstance(width, Layout):
            width = width.width
        assert isinstance(width, int)
        assert width >= 0
        return width

    def partition_points_signals(self, nameNone,
                                 src_loc_at=0):
        if name is None:
            name = Signal(src_loc_at=1 + src_loc_at).name
        return PartitionPoints({ i for i in self.part_indexes[1:-1] })

    def __repr__(self):
        return f"Layout({self.part_indexes}, width={self.width})"

    def __eq__(self, o):
        if isinstance(o, Layout):
            return self.part_indexes == o.part_indexes
        return NotImplemented

    def __hash__(self):
        return hash(self.part_indexes)

    def is_lane_valid(self, start, size):
        return start in self.__lane_starts_for_sizes.get(size, ())

    def lane_sizes(self):
        return self.__lane_starts_for_sizes.keys()

    def lane_starts_for_size(self, size):
        return self.__lane_starts_for_sizes[size].keys()

    def lanes_for_size(self, size):
        for start in self.lane_starts_for_size(size):
            yield Lane(start, size, self)

    def lanes(self):
        for size in self.lane_sizes():
            yield from self.lanes_for_size(size)

    def is_compatible(self, other):
        other = Layout.cast(other)
        return len(self.part_indexes) == len(other.part_indexes)

    def translate_lane_to(self, lane, target_layout):
        assert lane.layout == self
        target_layout = Layout.cast(target_layout)
        assert self.is_compatible(target_layout)
        start_index = self.part_indexes.index(lane.start)
        end_index = self.part_indexes.index(lane.end)
        target_start = target_layout.part_indexes[start_index]
        target_end = target_layout.part_indexes[end_index]
        return Lane(target_start, target_end - target_start, target_layout)


@final
class Lane:
    def __init__(self, start, size, layout):
        self.layout = Layout.cast(layout)
        assert self.layout.is_lane_valid(start, size)
        self.start = start
        self.size = size

    def __repr__(self):
        return (f"Lane(start={self.start}, size={self.size}, "
                f"layout={self.layout})")

    def __eq__(self, o):
        if isinstance(o, Lane):
            return self.start == o.start and self.size == o.size \
                and self.layout == o.layout
        return NotImplemented

    def __hash__(self):
        return hash((self.start, self.size, self.layout))

    def as_slice(self):
        return slice(self.start, self.end)

    @property
    def end(self):
        return self.start + self.size

    def translate_to(self, target_layout):
        return self.layout.translate_lane_to(self, target_layout)

    @overload
    def is_active(self, partition_points): ...

    @overload
    def is_active(self, partition_points): ...

    @overload
    def is_active(self, partition_points): ...

    @overload
    def is_active(self, partition_points): ...

    def is_active(self, partition_points):
        def get_partition_point(index, invert):
            if index == 0 or index == len(self.layout.part_indexes) - 1:
                return True
            if isinstance(partition_points, Sequence):
                retval = partition_points[index]
            else:
                retval = partition_points[self.layout.part_indexes[index]]
            if isinstance(retval, bool):
                if invert:
                    return not retval
                return retval
            retval = Value.cast(retval)
            if invert:
                return ~retval
            return retval

        start_index = self.layout.part_indexes.index(self.start)
        end_index = self.layout.part_indexes.index(self.end)
        retval = get_partition_point(start_index, False) \
            & get_partition_point(end_index, False)
        for i in range(start_index + 1, end_index):
            retval &= get_partition_point(i, True)

        return retval


class PartitionedSignalTester:

    def __init__(self, m, operation, reference, *layouts,
                 src_loc_at=0, additional_case_count=30,
                 special_cases=(), seed=""):
        self.m = m
        self.operation = operation
        self.reference = reference
        self.layouts = []
        self.inputs = []
        for layout in layouts:
            layout = Layout.cast(layout)
            if len(self.layouts) > 0:
                assert self.layouts[0].is_compatible(layout)
            self.layouts.append(layout)
            name = f"input_{len(self.inputs)}"
            ps = PartitionedSignal(
                layout.partition_points_signals(name=name,
                                                src_loc_at=1 + src_loc_at),
                layout.width,
                name=name)
            ps.set_module(m)
            self.inputs.append(ps)
        assert len(self.layouts) != 0, "must have at least one input layout"
        for i in range(1, len(self.inputs)):
            for j in range(1, len(self.layouts[0].part_indexes) - 1):
                lhs_part_point = self.layouts[i].part_indexes[j]
                rhs_part_point = self.layouts[0].part_indexes[j]
                lhs = self.inputs[i].partpoints[lhs_part_point]
                rhs = self.inputs[0].partpoints[rhs_part_point]
                m.d.comb += lhs.eq(rhs)
        self.special_cases = list(special_cases)
        self.case_count = additional_case_count + len(self.special_cases)
        self.seed = seed
        self.case_number = Signal(64)
        self.test_output = operation(tuple(self.inputs))
        assert isinstance(self.test_output, PartitionedSignal)
        self.test_output_layout = Layout(
            self.test_output.partpoints, self.test_output.sig.width)
        assert self.test_output_layout.is_compatible(self.layouts[0])
        self.reference_output_values = {
            lane, tuple(
                inp.sig[lane.translate_to(layout).as_slice()]
                for inp, layout in zip(self.inputs, self.layouts))
            for lane in self.layouts[0].lanes()
        }
        self.reference_outputs = {
            lane, name=f"reference_output_{lane.start}_{lane.size}")
            for lane, value in self.reference_output_values.items()
        }
        for lane, value in self.reference_output_values.items():
            m.d.comb += self.reference_outputs[lane].eq(value)

    def __hash_256(self, v):
        return int.from_bytes(
            sha256(bytes(self.seed + v, encoding='utf-8')).digest(),
            byteorder='little'
        )

    def __hash(self, v, bits):
        retval = 0
        for i in range(0, bits, 256):
            retval <<= 256
            retval |= self.__hash_256(f" {v} {i}")
        return retval & ((1 << bits) - 1)

    def __get_case(self, case_number):
        if case_number < len(self.special_cases):
            return self.special_cases[case_number]
        trial = 0
        bits = self.__hash(f"{case_number} trial {trial}",
                           self.layouts[0].part_signal_count)
        bits |= 1 | (1 << len(self.layouts[0].part_indexes)) | (bits << 1)
        part_starts = tuple(
            (bits & (1 << i)) != 0
            for i in range(len(self.layouts[0].part_indexes)))
        inputs = tuple(self.__hash(f"{case_number} input {i}",
                                   self.layouts[i].width)
                       for i in range(len(self.layouts)))
        return part_starts, inputs

    def __format_case(self, case):
        part_starts, inputs = case
        str_inputs = [hex(i) for i in inputs]
        return f"part_starts={part_starts}, inputs={str_inputs}"

    def __setup_case(self, case_number, case=None):
        if case is None:
            case = self.__get_case(case_number)
        yield self.case_number.eq(case_number)
        part_starts, inputs = case
        part_indexes = self.layouts[0].part_indexes
        assert len(part_starts) == len(part_indexes)
        for i in range(1, len(part_starts) - 1):
            yield self.inputs[0].partpoints[part_indexes[i]].eq(part_starts[i])
        for i in range(len(self.inputs)):
            yield self.inputs[i].sig.eq(inputs[i])

    def run_sim(self, test_case, *,
                engine: Optional[str] = None,
                base_path: _StrPath = "sim_test_out"):
        if engine is None:
            sim = Simulator(self.m)
        else:
            sim = Simulator(self.m, engine=engine)

        def check_active_lane(lane):
            reference = yield self.reference_outputs[lane]
            output = yield self.test_output.sig[
                lane.translate_to(self.test_output_layout).as_slice()]
            test_case.assertEqual(hex(reference), hex(output))

        def check_case(case):
            part_starts, inputs = case
            for i in range(1, len(self.layouts[0].part_indexes) - 1):
                part_point = yield self.test_output.partpoints[
                    self.test_output_layout.part_indexes[i]]
                test_case.assertEqual(part_point, part_starts[i])
            for lane in self.layouts[0].lanes():
                with test_case.subTest(lane=lane):
                    active = lane.is_active(part_starts)
                    if active:
                        yield from check_active_lane(lane)

        def process():
            for case_number in range(self.case_count):
                with test_case.subTest(case_number=str(case_number)):
                    case = self.__get_case(case_number)
                    with test_case.subTest(case=self.__format_case(case)):
                        yield from self.__setup_case(case_number, case)
                        yield Delay(1e-6)
                        yield from check_case(case)
        sim.add_process(process)
        path = get_test_path(test_case, base_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        vcd_path = path.with_suffix(".vcd")
        gtkw_path = path.with_suffix(".gtkw")
        traces = [self.case_number]
        for i in self.layouts[0].part_indexes[1:-1]:
            traces.append(self.inputs[0].partpoints[i])
        for inp in self.inputs:
            traces.append(inp.sig)
        traces.extend(self.reference_outputs.values())
        traces.append(self.test_output.sig)
        with sim.write_vcd(vcd_path.open("wt", encoding="utf-8"),
                           gtkw_path.open("wt", encoding="utf-8"),
                           traces=traces):
            sim.run()

    def run_formal(self, test_case, **kwargs):
        for part_point in self.inputs[0].partpoints.values():
            self.m.d.comb += part_point.eq(AnyConst(1))
        for i in range(len(self.inputs)):
            s = self.inputs[i].sig
            self.m.d.comb += s.eq(AnyConst(s.shape()))
        for i in range(1, len(self.layouts[0].part_indexes) - 1):
            in_part_point = self.inputs[0].partpoints[
                self.layouts[0].part_indexes[i]]
            out_part_point = self.test_output.partpoints[
                self.test_output_layout.part_indexes[i]]
            self.m.d.comb += Assert(in_part_point == out_part_point)

        def check_active_lane(lane):
            reference = self.reference_outputs[lane]
            output = self.test_output.sig[
                lane.translate_to(self.test_output_layout).as_slice()]
            yield Assert(reference == output)

        for lane in self.layouts[0].lanes():
            with test_case.subTest(lane=lane):
                a = check_active_lane(lane)
                with self.m.If(lane.is_active(self.inputs[0].partpoints)):
                    self.m.d.comb += a
        formal(test_case, self.m, **kwargs)
