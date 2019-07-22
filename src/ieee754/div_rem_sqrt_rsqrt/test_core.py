#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

from .core import (DivPipeCoreConfig, DivPipeCoreSetupStage,
                   DivPipeCoreCalculateStage, DivPipeCoreFinalStage,
                   DivPipeCoreOperation, DivPipeCoreInputData,
                   DivPipeCoreInterstageData, DivPipeCoreOutputData)
from .algorithm import (FixedUDivRemSqrtRSqrt, Fixed, Operation, div_rem,
                        fixed_sqrt, fixed_rsqrt)
import unittest
from nmigen import Module, Elaboratable, Signal
from nmigen.hdl.ir import Fragment
from nmigen.back import rtlil
from nmigen.back.pysim import Simulator, Delay, Tick
from itertools import chain


def show_fixed(bits, fract_width, bit_width):
    fixed = Fixed.from_bits(bits, fract_width, bit_width, False)
    return f"{str(fixed)}:{repr(fixed)}"


def get_core_op(alg_op):
    if alg_op is Operation.UDivRem:
        return DivPipeCoreOperation.UDivRem
    if alg_op is Operation.SqrtRem:
        return DivPipeCoreOperation.SqrtRem
    assert alg_op is Operation.RSqrtRem
    return DivPipeCoreOperation.RSqrtRem


class TestCaseData:
    __test__ = False  # make pytest ignore class

    def __init__(self,
                 dividend,
                 divisor_radicand,
                 alg_op,
                 quotient_root,
                 remainder,
                 core_config):
        self.dividend = dividend
        self.divisor_radicand = divisor_radicand
        self.alg_op = alg_op
        self.quotient_root = quotient_root
        self.remainder = remainder
        self.core_config = core_config

    @property
    def core_op(self):
        return get_core_op(self.alg_op)

    def __str__(self):
        bit_width = self.core_config.bit_width
        fract_width = self.core_config.fract_width
        dividend_str = show_fixed(self.dividend,
                                  fract_width * 2,
                                  bit_width + fract_width)
        divisor_radicand_str = show_fixed(self.divisor_radicand,
                                          fract_width,
                                          bit_width)
        quotient_root_str = show_fixed(self.quotient_root,
                                       fract_width,
                                       bit_width)
        remainder_str = show_fixed(self.remainder,
                                   fract_width * 3,
                                   bit_width * 3)
        return f"{{dividend={dividend_str}, " \
            + f"divisor_radicand={divisor_radicand_str}, " \
            + f"op={self.alg_op.name}, " \
            + f"quotient_root={quotient_root_str}, " \
            + f"remainder={remainder_str}, " \
            + f"config={self.core_config}}}"


def generate_test_case(core_config, dividend, divisor_radicand, alg_op):
    bit_width = core_config.bit_width
    fract_width = core_config.fract_width
    obj = FixedUDivRemSqrtRSqrt(dividend,
                                divisor_radicand,
                                alg_op,
                                bit_width,
                                fract_width,
                                core_config.log2_radix)
    obj.calculate()
    yield TestCaseData(dividend,
                       divisor_radicand,
                       alg_op,
                       obj.quotient_root,
                       obj.remainder,
                       core_config)


def shifted_ints(total_bits, int_bits):
    """ Generate a sequence like a generalized binary version of A037124.

        See https://oeis.org/A037124

        Generates the sequence of all non-negative integers ``n`` in ascending
        order with no repeats where ``n < (1 << total_bits) and n == (v << i)``
        where ``i`` is a non-negative integer and ``v`` is a non-negative
        integer less than ``1 << int_bits``.
    """
    n = 0
    while n < (1 << total_bits):
        yield n
        if n < (1 << int_bits):
            n += 1
        else:
            n += 1 << (n.bit_length() - int_bits)


def partitioned_ints(bit_width):
    """ Get ints with all 1s on one side and 0s on the other. """
    for i in range(bit_width):
        yield (-1 << i) & ((1 << bit_width) - 1)
        yield (1 << (i + 1)) - 1


class TestShiftedInts(unittest.TestCase):
    def test(self):
        expected = [0x000,
                    0x001,
                    0x002, 0x003,
                    0x004, 0x005, 0x006, 0x007,
                    0x008, 0x009, 0x00A, 0x00B, 0x00C, 0x00D, 0x00E, 0x00F,
                    0x010, 0x012, 0x014, 0x016, 0x018, 0x01A, 0x01C, 0x01E,
                    0x020, 0x024, 0x028, 0x02C, 0x030, 0x034, 0x038, 0x03C,
                    0x040, 0x048, 0x050, 0x058, 0x060, 0x068, 0x070, 0x078,
                    0x080, 0x090, 0x0A0, 0x0B0, 0x0C0, 0x0D0, 0x0E0, 0x0F0,
                    0x100, 0x120, 0x140, 0x160, 0x180, 0x1A0, 0x1C0, 0x1E0,
                    0x200, 0x240, 0x280, 0x2C0, 0x300, 0x340, 0x380, 0x3C0,
                    0x400, 0x480, 0x500, 0x580, 0x600, 0x680, 0x700, 0x780,
                    0x800, 0x900, 0xA00, 0xB00, 0xC00, 0xD00, 0xE00, 0xF00]
        self.assertEqual(list(shifted_ints(12, 4)), expected)


def get_test_cases(core_config,
                   dividends=None,
                   divisors=None,
                   radicands=None):
    if dividends is None:
        dividend_width = core_config.bit_width + core_config.fract_width
        dividends = [*shifted_ints(dividend_width,
                                   max(3, core_config.log2_radix)),
                     *partitioned_ints(dividend_width)]
    else:
        assert isinstance(dividends, list)
    if divisors is None:
        divisors = [*shifted_ints(core_config.bit_width,
                                  max(3, core_config.log2_radix)),
                    *partitioned_ints(core_config.bit_width)]
    else:
        assert isinstance(divisors, list)
    if radicands is None:
        radicands = [*shifted_ints(core_config.bit_width, 5),
                     *partitioned_ints(core_config.bit_width)]
    else:
        assert isinstance(radicands, list)

    for alg_op in reversed(Operation):  # put UDivRem at end
        if alg_op is Operation.UDivRem:
            for dividend in dividends:
                for divisor in divisors:
                    yield from generate_test_case(core_config,
                                                  dividend,
                                                  divisor,
                                                  alg_op)
        else:
            for radicand in radicands:
                yield from generate_test_case(core_config,
                                              0,
                                              radicand,
                                              alg_op)


class DivPipeCoreTestPipeline(Elaboratable):
    def __init__(self, core_config, sync):
        self.setup_stage = DivPipeCoreSetupStage(core_config)
        self.calculate_stages = [
            DivPipeCoreCalculateStage(core_config, stage_index)
            for stage_index in range(core_config.n_stages)]
        self.final_stage = DivPipeCoreFinalStage(core_config)
        self.interstage_signals = [
            DivPipeCoreInterstageData(core_config, reset_less=True)
            for i in range(core_config.n_stages + 1)]
        self.i = DivPipeCoreInputData(core_config, reset_less=True)
        self.o = DivPipeCoreOutputData(core_config, reset_less=True)
        self.sync = sync

    def elaborate(self, platform):
        m = Module()
        stages = [self.setup_stage, *self.calculate_stages, self.final_stage]
        stage_inputs = [self.i, *self.interstage_signals]
        stage_outputs = [*self.interstage_signals, self.o]
        for stage, input, output in zip(stages, stage_inputs, stage_outputs):
            stage.setup(m, input)
            assignments = output.eq(stage.process(input))
            if self.sync:
                m.d.sync += assignments
            else:
                m.d.comb += assignments
        return m

    def traces(self):
        yield from self.i
        # for interstage_signal in self.interstage_signals:
        #     yield from interstage_signal
        yield from self.o


class TestDivPipeCore(unittest.TestCase):
    def handle_config(self,
                      core_config,
                      test_cases=None,
                      sync=True):
        if test_cases is None:
            test_cases = get_test_cases(core_config)
        test_cases = list(test_cases)
        base_name = f"test_div_pipe_core_bit_width_{core_config.bit_width}"
        base_name += f"_fract_width_{core_config.fract_width}"
        base_name += f"_radix_{1 << core_config.log2_radix}"
        if not sync:
            base_name += "_comb"
        with self.subTest(part="synthesize"):
            dut = DivPipeCoreTestPipeline(core_config, sync)
            vl = rtlil.convert(dut, ports=[*dut.i, *dut.o])
            with open(f"{base_name}.il", "w") as f:
                f.write(vl)
        dut = DivPipeCoreTestPipeline(core_config, sync)
        with Simulator(dut,
                       vcd_file=open(f"{base_name}.vcd", "w"),
                       gtkw_file=open(f"{base_name}.gtkw", "w"),
                       traces=[*dut.traces()]) as sim:
            def generate_process():
                for test_case in test_cases:
                    yield Tick()
                    yield dut.i.dividend.eq(test_case.dividend)
                    yield dut.i.divisor_radicand.eq(test_case.divisor_radicand)
                    yield dut.i.operation.eq(int(test_case.core_op))
                    yield Delay(0.9e-6)

            def check_process():
                # sync with generator
                if sync:
                    yield
                    for _ in range(core_config.n_stages):
                        yield
                    yield

                # now synched with generator
                for test_case in test_cases:
                    yield Tick()
                    yield Delay(0.9e-6)
                    quotient_root = (yield dut.o.quotient_root)
                    remainder = (yield dut.o.remainder)
                    with self.subTest(test_case=str(test_case)):
                        self.assertEqual(quotient_root,
                                         test_case.quotient_root)
                        self.assertEqual(remainder, test_case.remainder)
            sim.add_clock(2e-6)
            sim.add_sync_process(generate_process)
            sim.add_sync_process(check_process)
            sim.run()

    def test_bit_width_2_fract_width_1_radix_2_comb(self):
        self.handle_config(DivPipeCoreConfig(bit_width=2,
                                             fract_width=1,
                                             log2_radix=1),
                           sync=False)

    def test_bit_width_2_fract_width_1_radix_2(self):
        self.handle_config(DivPipeCoreConfig(bit_width=2,
                                             fract_width=1,
                                             log2_radix=1))

    def test_bit_width_8_fract_width_4_radix_2_comb(self):
        self.handle_config(DivPipeCoreConfig(bit_width=8,
                                             fract_width=4,
                                             log2_radix=1),
                           sync=False)

    def test_bit_width_8_fract_width_4_radix_2(self):
        self.handle_config(DivPipeCoreConfig(bit_width=8,
                                             fract_width=4,
                                             log2_radix=1))

    def test_bit_width_32_fract_width_24_radix_8_comb(self):
        self.handle_config(DivPipeCoreConfig(bit_width=32,
                                             fract_width=24,
                                             log2_radix=3),
                           sync=False)

    def test_bit_width_32_fract_width_24_radix_8(self):
        self.handle_config(DivPipeCoreConfig(bit_width=32,
                                             fract_width=24,
                                             log2_radix=3))

    def test_bit_width_32_fract_width_28_radix_8_comb(self):
        self.handle_config(DivPipeCoreConfig(bit_width=32,
                                             fract_width=28,
                                             log2_radix=3),
                           sync=False)

    def test_bit_width_32_fract_width_28_radix_8(self):
        self.handle_config(DivPipeCoreConfig(bit_width=32,
                                             fract_width=28,
                                             log2_radix=3))

    # FIXME: add more test_* functions


if __name__ == '__main__':
    unittest.main()
