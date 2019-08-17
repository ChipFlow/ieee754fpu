#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

from ieee754.part_mul_add.multiply import \
                            (PartitionPoints, PartitionedAdder, AddReduce,
                            Mul8_16_32_64, OP_MUL_LOW, OP_MUL_SIGNED_HIGH,
                            OP_MUL_SIGNED_UNSIGNED_HIGH, OP_MUL_UNSIGNED_HIGH)
from nmigen import Signal, Module
from nmigen.back.pysim import Simulator, Delay, Tick, Passive
from nmigen.hdl.ast import Assign, Value
from typing import Any, Generator, List, Union, Optional, Tuple, Iterable
import unittest
from hashlib import sha256
import enum
import pdb


def create_simulator(module: Any,
                     traces: List[Signal],
                     test_name: str) -> Simulator:
    return Simulator(module,
                     vcd_file=open(test_name + ".vcd", "w"),
                     gtkw_file=open(test_name + ".gtkw", "w"),
                     traces=traces)


AsyncProcessCommand = Union[Delay, Tick, Passive, Assign, Value]
ProcessCommand = Optional[AsyncProcessCommand]
AsyncProcessGenerator = Generator[AsyncProcessCommand, Union[int, None], None]
ProcessGenerator = Generator[ProcessCommand, Union[int, None], None]


class TestPartitionPoints(unittest.TestCase):
    def test(self) -> None:
        module = Module()
        width = 16
        mask = Signal(width)
        partition_point_10 = Signal()
        partition_points = PartitionPoints({1: True,
                                            5: False,
                                            10: partition_point_10})
        module.d.comb += mask.eq(partition_points.as_mask(width))
        with create_simulator(module,
                              [mask, partition_point_10],
                              "partition_points") as sim:
            def async_process() -> AsyncProcessGenerator:
                self.assertEqual((yield partition_points[1]), True)
                self.assertEqual((yield partition_points[5]), False)
                yield partition_point_10.eq(0)
                yield Delay(1e-6)
                self.assertEqual((yield mask), 0xFFFD)
                yield partition_point_10.eq(1)
                yield Delay(1e-6)
                self.assertEqual((yield mask), 0xFBFD)

            sim.add_process(async_process)
            sim.run()


class TestPartitionedAdder(unittest.TestCase):
    def test(self) -> None:
        width = 16
        partition_nibbles = Signal()
        partition_bytes = Signal()
        module = PartitionedAdder(width,
                                  {0x4: partition_nibbles,
                                   0x8: partition_bytes | partition_nibbles,
                                   0xC: partition_nibbles})
        with create_simulator(module,
                              [partition_nibbles,
                               partition_bytes,
                               module.a,
                               module.b,
                               module.output],
                              "partitioned_adder") as sim:
            def async_process() -> AsyncProcessGenerator:
                def test_add(msg_prefix: str,
                             *mask_list: Tuple[int, ...]) -> Any:
                    for a, b in [(0x0000, 0x0000),
                                 (0x1234, 0x1234),
                                 (0xABCD, 0xABCD),
                                 (0xFFFF, 0x0000),
                                 (0x0000, 0x0000),
                                 (0xFFFF, 0xFFFF),
                                 (0x0000, 0xFFFF)]:
                        yield module.a.eq(a)
                        yield module.b.eq(b)
                        yield Delay(1e-6)
                        y = 0
                        for mask in mask_list:
                            y |= mask & ((a & mask) + (b & mask))
                        output = (yield module.output)
                        msg = f"{msg_prefix}: 0x{a:X} + 0x{b:X}" + \
                            f" => 0x{y:X} != 0x{output:X}"
                        self.assertEqual(y, output, msg)
                yield partition_nibbles.eq(0)
                yield partition_bytes.eq(0)
                yield from test_add("16-bit", 0xFFFF)
                yield partition_nibbles.eq(0)
                yield partition_bytes.eq(1)
                yield from test_add("8-bit", 0xFF00, 0x00FF)
                yield partition_nibbles.eq(1)
                yield partition_bytes.eq(0)
                yield from test_add("4-bit", 0xF000, 0x0F00, 0x00F0, 0x000F)

            sim.add_process(async_process)
            sim.run()


class GenOrCheck(enum.Enum):
    Generate = enum.auto()
    Check = enum.auto()


class TestAddReduce(unittest.TestCase):
    def calculate_input_values(self,
                               input_count: int,
                               key: int,
                               extra_keys: List[int] = []
                               ) -> (List[int], List[str]):
        input_values = []
        input_values_str = []
        for i in range(input_count):
            if key == 0:
                value = 0
            elif key == 1:
                value = 0xFFFF
            elif key == 2:
                value = 0x0111
            else:
                hash_input = f"{input_count} {i} {key} {extra_keys}"
                hash = sha256(hash_input.encode()).digest()
                value = int.from_bytes(hash, byteorder="little")
                value &= 0xFFFF
            input_values.append(value)
            input_values_str.append(f"0x{value:04X}")
        return input_values, input_values_str

    def subtest_value(self,
                      inputs: List[Signal],
                      module: AddReduce,
                      mask_list: List[int],
                      gen_or_check: GenOrCheck,
                      values: List[int]) -> AsyncProcessGenerator:
        if gen_or_check == GenOrCheck.Generate:
            for i, v in zip(inputs, values):
                yield i.eq(v)
        yield Delay(1e-6)
        y = 0
        for mask in mask_list:
            v = 0
            for value in values:
                v += value & mask
            y |= mask & v
        output = (yield module.output)
        if gen_or_check == GenOrCheck.Check:
            self.assertEqual(y, output, f"0x{y:X} != 0x{output:X}")
        yield Tick()

    def subtest_key(self,
                    input_count: int,
                    inputs: List[Signal],
                    module: AddReduce,
                    key: int,
                    mask_list: List[int],
                    gen_or_check: GenOrCheck) -> AsyncProcessGenerator:
        values, values_str = self.calculate_input_values(input_count, key)
        if gen_or_check == GenOrCheck.Check:
            with self.subTest(inputs=values_str):
                yield from self.subtest_value(inputs,
                                              module,
                                              mask_list,
                                              gen_or_check,
                                              values)
        else:
            yield from self.subtest_value(inputs,
                                          module,
                                          mask_list,
                                          gen_or_check,
                                          values)

    def subtest_run_sim(self,
                        input_count: int,
                        sim: Simulator,
                        partition_4: Signal,
                        partition_8: Signal,
                        inputs: List[Signal],
                        module: AddReduce,
                        delay_cycles: int) -> None:
        def generic_process(gen_or_check: GenOrCheck) -> AsyncProcessGenerator:
            for partition_4_value, partition_8_value, mask_list in [
                    (0, 0, [0xFFFF]),
                    (0, 1, [0xFF00, 0x00FF]),
                    (1, 0, [0xFFF0, 0x000F]),
                    (1, 1, [0xFF00, 0x00F0, 0x000F])]:
                key_count = 8
                if gen_or_check == GenOrCheck.Check:
                    with self.subTest(partition_4=partition_4_value,
                                      partition_8=partition_8_value):
                        for key in range(key_count):
                            with self.subTest(key=key):
                                yield from self.subtest_key(input_count,
                                                            inputs,
                                                            module,
                                                            key,
                                                            mask_list,
                                                            gen_or_check)
                else:
                    if gen_or_check == GenOrCheck.Generate:
                        yield partition_4.eq(partition_4_value)
                        yield partition_8.eq(partition_8_value)
                    for key in range(key_count):
                        yield from self.subtest_key(input_count,
                                                    inputs,
                                                    module,
                                                    key,
                                                    mask_list,
                                                    gen_or_check)

        def generate_process() -> AsyncProcessGenerator:
            yield from generic_process(GenOrCheck.Generate)

        def check_process() -> AsyncProcessGenerator:
            if delay_cycles != 0:
                for _ in range(delay_cycles):
                    yield Tick()
            yield from generic_process(GenOrCheck.Check)

        sim.add_clock(2e-6)
        sim.add_process(generate_process)
        sim.add_process(check_process)
        sim.run()

    def subtest_file(self,
                     input_count: int,
                     register_levels: List[int]) -> None:
        max_level = AddReduce.get_max_level(input_count)
        for level in register_levels:
            if level > max_level:
                return
        partition_4 = Signal()
        partition_8 = Signal()
        partition_points = PartitionPoints()
        partition_points[4] = partition_4
        partition_points[8] = partition_8
        width = 16
        inputs = [Signal(width, name=f"input_{i}")
                  for i in range(input_count)]
        module = AddReduce(inputs,
                           width,
                           register_levels,
                           partition_points)
        file_name = "add_reduce"
        if len(register_levels) != 0:
            file_name += f"-{'_'.join(map(repr, register_levels))}"
        file_name += f"-{input_count:02d}"
        with create_simulator(module,
                              [partition_4,
                               partition_8,
                               *inputs,
                               module.output],
                              file_name) as sim:
            self.subtest_run_sim(input_count,
                                 sim,
                                 partition_4,
                                 partition_8,
                                 inputs,
                                 module,
                                 len(register_levels))

    def subtest_register_levels(self, register_levels: List[int]) -> None:
        for input_count in range(0, 16):
            with self.subTest(input_count=input_count,
                              register_levels=repr(register_levels)):
                self.subtest_file(input_count, register_levels)

    def test_empty(self) -> None:
        self.subtest_register_levels([])

    def test_0(self) -> None:
        self.subtest_register_levels([0])

    def test_1(self) -> None:
        self.subtest_register_levels([1])

    def test_2(self) -> None:
        self.subtest_register_levels([2])

    def test_3(self) -> None:
        self.subtest_register_levels([3])

    def test_4(self) -> None:
        self.subtest_register_levels([4])

    def test_5(self) -> None:
        self.subtest_register_levels([5])

    def test_0(self) -> None:
        self.subtest_register_levels([0])

    def test_0_1(self) -> None:
        self.subtest_register_levels([0, 1])

    def test_0_1_2(self) -> None:
        self.subtest_register_levels([0, 1, 2])

    def test_0_1_2_3(self) -> None:
        self.subtest_register_levels([0, 1, 2, 3])

    def test_0_1_2_3_4(self) -> None:
        self.subtest_register_levels([0, 1, 2, 3, 4])

    def test_0_1_2_3_4_5(self) -> None:
        self.subtest_register_levels([0, 1, 2, 3, 4, 5])

    def test_0_2(self) -> None:
        self.subtest_register_levels([0, 2])

    def test_0_3(self) -> None:
        self.subtest_register_levels([0, 3])

    def test_0_4(self) -> None:
        self.subtest_register_levels([0, 4])

    def test_0_5(self) -> None:
        self.subtest_register_levels([0, 5])


class SIMDMulLane:
    def __init__(self,
                 a_signed: bool,
                 b_signed: bool,
                 bit_width: int,
                 high_half: bool):
        self.a_signed = a_signed
        self.b_signed = b_signed
        self.bit_width = bit_width
        self.high_half = high_half

    def __repr__(self):
        return f"SIMDMulLane({self.a_signed}, {self.b_signed}, " +\
            f"{self.bit_width}, {self.high_half})"


class TestMul8_16_32_64(unittest.TestCase):
    @staticmethod
    def simd_mul(a: int, b: int, lanes: List[SIMDMulLane]) -> Tuple[int, int]:
        output = 0
        intermediate_output = 0
        shift = 0
        for lane in lanes:
            a_signed = lane.a_signed or not lane.high_half
            b_signed = lane.b_signed or not lane.high_half
            mask = (1 << lane.bit_width) - 1
            sign_bit = 1 << (lane.bit_width - 1)
            a_part = (a >> shift) & mask
            if a_signed and (a_part & sign_bit) != 0:
                a_part -= 1 << lane.bit_width
            b_part = (b >> shift) & mask
            if b_signed and (b_part & sign_bit) != 0:
                b_part -= 1 << lane.bit_width
            value = a_part * b_part
            value &= (1 << (lane.bit_width * 2)) - 1
            intermediate_output |= value << (shift * 2)
            if lane.high_half:
                value >>= lane.bit_width
            value &= mask
            output |= value << shift
            shift += lane.bit_width
        return output, intermediate_output

    @staticmethod
    def get_test_cases(lanes: List[SIMDMulLane],
                       keys: Iterable[int]) -> Iterable[Tuple[int, int]]:
        mask = (1 << 64) - 1
        for i in range(8):
            hash_input = f"{i} {lanes} {list(keys)}"
            hash = sha256(hash_input.encode()).digest()
            value = int.from_bytes(hash, byteorder="little")
            yield (value & mask, value >> 64)
        a = 0
        b = 0
        shift = 0
        for lane in lanes:
            a |= 1 << (shift + lane.bit_width - 1)
            b |= 1 << (shift + lane.bit_width - 1)
            shift += lane.bit_width
        yield a, b

    def test_simd_mul_lane(self):
        self.assertEqual(f"{SIMDMulLane(True, True, 8, False)}",
                         "SIMDMulLane(True, True, 8, False)")

    def test_simd_mul(self):
        lanes = [SIMDMulLane(True,
                             True,
                             8,
                             True),
                 SIMDMulLane(False,
                             False,
                             8,
                             True),
                 SIMDMulLane(True,
                             True,
                             16,
                             False),
                 SIMDMulLane(True,
                             False,
                             32,
                             True)]
        a = 0x0123456789ABCDEF
        b = 0xFEDCBA9876543210
        output = 0x0121FA00FE1C28FE
        intermediate_output = 0x0121FA0023E20B28C94DFE1C280AFEF0
        self.assertEqual(self.simd_mul(a, b, lanes),
                         (output, intermediate_output))
        a = 0x8123456789ABCDEF
        b = 0xFEDCBA9876543210
        output = 0x81B39CB4FE1C28FE
        intermediate_output = 0x81B39CB423E20B28C94DFE1C280AFEF0
        self.assertEqual(self.simd_mul(a, b, lanes),
                         (output, intermediate_output))

    def test_signed_mul_from_unsigned(self):
        for i in range(0, 0x10):
            for j in range(0, 0x10):
                si = i if i & 8 else i - 0x10  # signed i
                sj = j if j & 8 else j - 0x10  # signed j
                mulu = i * j
                mulsu = si * j
                mul = si * sj
                with self.subTest(i=i, j=j, si=si, sj=sj,
                                  mulu=mulu, mulsu=mulsu, mul=mul):
                    mulsu2 = mulu
                    if si < 0:
                        mulsu2 += ~j << 4
                        mulsu2 += 1 << 4
                    self.assertEqual(mulsu & 0xFF, mulsu2 & 0xFF)
                    mul2 = mulsu2
                    if sj < 0:
                        mul2 += ~i << 4
                        mul2 += 1 << 4
                    self.assertEqual(mul & 0xFF, mul2 & 0xFF)

    def subtest_value(self,
                      a: int,
                      b: int,
                      module: Mul8_16_32_64,
                      lanes: List[SIMDMulLane],
                      gen_or_check: GenOrCheck) -> AsyncProcessGenerator:
        if gen_or_check == GenOrCheck.Generate:
            yield module.a.eq(a)
            yield module.b.eq(b)
        output2, intermediate_output2 = self.simd_mul(a, b, lanes)
        yield Delay(1e-6)
        if gen_or_check == GenOrCheck.Check:
            intermediate_output = (yield module._intermediate_output)
            self.assertEqual(intermediate_output,
                             intermediate_output2,
                             f"0x{intermediate_output:X} "
                             + f"!= 0x{intermediate_output2:X}")
            output = (yield module.output)
            self.assertEqual(output, output2, f"0x{output:X} != 0x{output2:X}")
        yield Tick()

    def subtest_lanes_2(self,
                        lanes: List[SIMDMulLane],
                        module: Mul8_16_32_64,
                        gen_or_check: GenOrCheck) -> AsyncProcessGenerator:
        bit_index = 8
        part_index = 0
        for lane in lanes:
            if lane.high_half:
                if lane.a_signed:
                    if lane.b_signed:
                        op = OP_MUL_SIGNED_HIGH
                    else:
                        op = OP_MUL_SIGNED_UNSIGNED_HIGH
                else:
                    self.assertFalse(lane.b_signed,
                                     "unsigned * signed not supported")
                    op = OP_MUL_UNSIGNED_HIGH
            else:
                op = OP_MUL_LOW
            self.assertEqual(lane.bit_width % 8, 0)
            for i in range(lane.bit_width // 8):
                if gen_or_check == GenOrCheck.Generate:
                    yield module.part_ops[part_index].eq(op)
                part_index += 1
            for i in range(lane.bit_width // 8 - 1):
                if gen_or_check == GenOrCheck.Generate:
                    yield module.part_pts[bit_index].eq(0)
                bit_index += 8
            if bit_index < 64 and gen_or_check == GenOrCheck.Generate:
                yield module.part_pts[bit_index].eq(1)
            bit_index += 8
        self.assertEqual(part_index, 8)
        for a, b in self.get_test_cases(lanes, ()):
            if gen_or_check == GenOrCheck.Check:
                with self.subTest(a=f"{a:X}", b=f"{b:X}"):
                    yield from self.subtest_value(a, b, module, lanes, gen_or_check)
            else:
                yield from self.subtest_value(a, b, module, lanes, gen_or_check)

    def subtest_lanes(self,
                      lanes: List[SIMDMulLane],
                      module: Mul8_16_32_64,
                      gen_or_check: GenOrCheck) -> AsyncProcessGenerator:
        if gen_or_check == GenOrCheck.Check:
            with self.subTest(lanes=repr(lanes)):
                yield from self.subtest_lanes_2(lanes, module, gen_or_check)
        else:
            yield from self.subtest_lanes_2(lanes, module, gen_or_check)

    def subtest_file(self,
                     register_levels: List[int]) -> None:
        module = Mul8_16_32_64(register_levels)
        file_name = "mul8_16_32_64"
        if len(register_levels) != 0:
            file_name += f"-{'_'.join(map(repr, register_levels))}"
        ports = [module.a,
                 module.b,
                 module._intermediate_output,
                 module.output]
        ports.extend(module.part_ops)
        ports.extend(module.part_pts.values())
        with create_simulator(module, ports, file_name) as sim:
            def process(gen_or_check: GenOrCheck) -> AsyncProcessGenerator:
                for a_signed in False, True:
                    for b_signed in False, True:
                        if not a_signed and b_signed:
                            continue
                        for high_half in False, True:
                            if not high_half and not (a_signed and b_signed):
                                continue
                            yield from self.subtest_lanes(
                                [SIMDMulLane(a_signed,
                                             b_signed,
                                             64,
                                             high_half)],
                                module,
                                gen_or_check)
                            yield from self.subtest_lanes(
                                [SIMDMulLane(a_signed,
                                             b_signed,
                                             32,
                                             high_half)] * 2,
                                module,
                                gen_or_check)
                            yield from self.subtest_lanes(
                                [SIMDMulLane(a_signed,
                                             b_signed,
                                             16,
                                             high_half)] * 4,
                                module,
                                gen_or_check)
                            yield from self.subtest_lanes(
                                [SIMDMulLane(a_signed,
                                             b_signed,
                                             8,
                                             high_half)] * 8,
                                module,
                                gen_or_check)
                yield from self.subtest_lanes([SIMDMulLane(False,
                                                           False,
                                                           32,
                                                           True),
                                               SIMDMulLane(False,
                                                           False,
                                                           16,
                                                           True),
                                               SIMDMulLane(False,
                                                           False,
                                                           8,
                                                           True),
                                               SIMDMulLane(False,
                                                           False,
                                                           8,
                                                           True)],
                                              module,
                                              gen_or_check)
                yield from self.subtest_lanes([SIMDMulLane(True,
                                                           False,
                                                           32,
                                                           True),
                                               SIMDMulLane(True,
                                                           True,
                                                           16,
                                                           False),
                                               SIMDMulLane(True,
                                                           True,
                                                           8,
                                                           True),
                                               SIMDMulLane(False,
                                                           False,
                                                           8,
                                                           True)],
                                              module,
                                              gen_or_check)
                yield from self.subtest_lanes([SIMDMulLane(True,
                                                           True,
                                                           8,
                                                           True),
                                               SIMDMulLane(False,
                                                           False,
                                                           8,
                                                           True),
                                               SIMDMulLane(True,
                                                           True,
                                                           16,
                                                           False),
                                               SIMDMulLane(True,
                                                           False,
                                                           32,
                                                           True)],
                                              module,
                                              gen_or_check)

            def generate_process() -> AsyncProcessGenerator:
                yield from process(GenOrCheck.Generate)

            def check_process() -> AsyncProcessGenerator:
                if len(register_levels) != 0:
                    for _ in register_levels:
                        yield Tick()
                yield from process(GenOrCheck.Check)

            sim.add_clock(2e-6)
            sim.add_process(generate_process)
            sim.add_process(check_process)
            sim.run()

    def subtest_register_levels(self, register_levels: List[int]) -> None:
        with self.subTest(register_levels=repr(register_levels)):
            self.subtest_file(register_levels)

    def test_empty(self) -> None:
        self.subtest_register_levels([])

    def test_0(self) -> None:
        self.subtest_register_levels([0])

    def test_1(self) -> None:
        self.subtest_register_levels([1])

    def test_2(self) -> None:
        self.subtest_register_levels([2])

    def test_3(self) -> None:
        self.subtest_register_levels([3])

    def test_4(self) -> None:
        self.subtest_register_levels([4])

    def test_5(self) -> None:
        self.subtest_register_levels([5])

    def test_6(self) -> None:
        self.subtest_register_levels([6])

    def test_7(self) -> None:
        self.subtest_register_levels([7])

    def test_8(self) -> None:
        self.subtest_register_levels([8])

    def test_9(self) -> None:
        self.subtest_register_levels([9])

    def test_10(self) -> None:
        self.subtest_register_levels([10])

    def test_0(self) -> None:
        self.subtest_register_levels([0])

    def test_0_1(self) -> None:
        self.subtest_register_levels([0, 1])

    def test_0_1_2(self) -> None:
        self.subtest_register_levels([0, 1, 2])

    def test_0_1_2_3(self) -> None:
        self.subtest_register_levels([0, 1, 2, 3])

    def test_0_1_2_3_4(self) -> None:
        self.subtest_register_levels([0, 1, 2, 3, 4])

    def test_0_1_2_3_4_5(self) -> None:
        self.subtest_register_levels([0, 1, 2, 3, 4, 5])

    def test_0_1_2_3_4_5_6(self) -> None:
        self.subtest_register_levels([0, 1, 2, 3, 4, 5, 6])

    def test_0_1_2_3_4_5_6_7(self) -> None:
        self.subtest_register_levels([0, 1, 2, 3, 4, 5, 6, 7])

    def test_0_1_2_3_4_5_6_7_8(self) -> None:
        self.subtest_register_levels([0, 1, 2, 3, 4, 5, 6, 7, 8])

    def test_0_1_2_3_4_5_6_7_8_9(self) -> None:
        self.subtest_register_levels([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])

    def test_0_1_2_3_4_5_6_7_8_9_10(self) -> None:
        self.subtest_register_levels([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])

    def test_0_2(self) -> None:
        self.subtest_register_levels([0, 2])

    def test_0_3(self) -> None:
        self.subtest_register_levels([0, 3])

    def test_0_4(self) -> None:
        self.subtest_register_levels([0, 4])

    def test_0_5(self) -> None:
        self.subtest_register_levels([0, 5])

    def test_0_6(self) -> None:
        self.subtest_register_levels([0, 6])

    def test_0_7(self) -> None:
        self.subtest_register_levels([0, 7])

    def test_0_8(self) -> None:
        self.subtest_register_levels([0, 8])

    def test_0_9(self) -> None:
        self.subtest_register_levels([0, 9])

    def test_0_10(self) -> None:
        self.subtest_register_levels([0, 10])

if __name__ == '__main__':
    unittest.main()
