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
from nmigen import Module, Elaboratable
from nmigen.hdl.ir import Fragment
from nmigen.back import rtlil
from nmigen.back.pysim import Simulator, Delay, Tick


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
        dividend_str = show_fixed(dividend,
                                  fract_width * 2,
                                  bit_width + fract_width)
        divisor_radicand_str = show_fixed(divisor_radicand,
                                          fract_width,
                                          bit_width)
        quotient_root_str = self.show_fixed(quotient_root,
                                            fract_width,
                                            bit_width)
        remainder_str = self.show_fixed(remainder,
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
    if alg_op is Operation.UDivRem:
        if divisor_radicand == 0:
            return
        quotient_root, remainder = div_rem(dividend,
                                           divisor_radicand,
                                           bit_width * 3,
                                           False)
        remainder <<= fract_width
    elif alg_op is Operation.SqrtRem:
        root_remainder = fixed_sqrt(Fixed.from_bits(divisor_radicand,
                                                    fract_width,
                                                    bit_width,
                                                    False))
        quotient_root = root_remainder.root.bits
        remainder = root_remainder.remainder.bits << fract_width
    else:
        assert alg_op is Operation.RSqrtRem
        if divisor_radicand == 0:
            return
        root_remainder = fixed_rsqrt(Fixed.from_bits(divisor_radicand,
                                                     fract_width,
                                                     bit_width,
                                                     False))
        quotient_root = root_remainder.root.bits
        remainder = root_remainder.remainder.bits
    if quotient_root >= (1 << bit_width):
        return
    yield TestCaseData(dividend,
                       divisor_radicand,
                       alg_op,
                       quotient_root,
                       remainder,
                       core_config)


def get_test_cases(core_config,
                   dividend_range=None,
                   divisor_range=None,
                   radicand_range=None):
    if dividend_range is None:
        dividend_range = range(1 << (core_config.bit_width
                                     + core_config.fract_width))
    if divisor_range is None:
        divisor_range = range(1 << core_config.bit_width)
    if radicand_range is None:
        radicand_range = range(1 << core_config.bit_width)

    for alg_op in Operation:
        if alg_op is Operation.UDivRem:
            for dividend in dividend_range:
                for divisor in divisor_range:
                    yield from generate_test_case(core_config,
                                                  dividend,
                                                  divisor,
                                                  alg_op)
        else:
            for radicand in radicand_range:
                yield from generate_test_case(core_config,
                                              dividend,
                                              radicand,
                                              alg_op)


class DivPipeCoreTestPipeline(Elaboratable):
    def __init__(self, core_config):
        self.setup_stage = DivPipeCoreSetupStage(core_config)
        self.calculate_stages = [
            DivPipeCoreCalculateStage(core_config, stage_index)
            for stage_index in range(core_config.num_calculate_stages)]
        self.final_stage = DivPipeCoreFinalStage(core_config)
        self.interstage_signals = [
            DivPipeCoreInterstageData(core_config, reset_less=True)
            for i in range(core_config.num_calculate_stages + 1)]
        self.i = DivPipeCoreInputData(core_config, reset_less=True)
        self.o = DivPipeCoreOutputData(core_config, reset_less=True)

    def elaborate(self, platform):
        m = Module()
        stages = [self.setup_stage, *self.calculate_stages, self.final_stage]
        stage_inputs = [self.i, *self.interstage_signals]
        stage_outputs = [*self.interstage_signals, self.o]
        for stage, input, output in zip(stages, stage_inputs, stage_outputs):
            stage.setup(m, input)
            m.d.sync += output.eq(stage.process(input))

        return m

    def traces(self):
        yield from self.i
        for interstage_signal in self.interstage_signals:
            yield from interstage_signal
        yield from self.o


class TestDivPipeCore(unittest.TestCase):
    def handle_case(self,
                    core_config,
                    dividend_range=None,
                    divisor_range=None,
                    radicand_range=None):
        def gen_test_cases():
            yield from get_test_cases(core_config,
                                      dividend_range,
                                      divisor_range,
                                      radicand_range)
        base_name = f"div_pipe_core_bit_width_{core_config.bit_width}"
        base_name += f"_fract_width_{core_config.fract_width}"
        base_name += f"_radix_{1 << core_config.log2_radix}"
        with self.subTest(part="synthesize"):
            dut = DivPipeCoreTestPipeline(core_config)
            vl = rtlil.convert(dut, ports=[*dut.i, *dut.o])
            with open(f"{base_name}.il", "w") as f:
                f.write(vl)
        dut = DivPipeCoreTestPipeline(core_config)
        with Simulator(dut,
                       vcd_file=f"{base_name}.vcd",
                       gtkw_file=f"{base_name}.gtkw",
                       traces=[*dut.traces()]) as sim:
            def generate_process():
                for test_case in gen_test_cases():
                    yield dut.i.dividend.eq(test_case.dividend)
                    yield dut.i.divisor_radicand.eq(test_case.divisor_radicand)
                    yield dut.i.operation.eq(test_case.core_op)
                    yield Delay(1e-6)
                    yield Tick()

            def check_process():
                # sync with generator
                yield
                for _ in core_config.num_calculate_stages:
                    yield
                yield

                # now synched with generator
                for test_case in gen_test_cases():
                    yield Delay(1e-6)
                    quotient_root = (yield dut.o.quotient_root)
                    remainder = (yield dut.o.remainder)
                    with self.subTest(test_case=str(test_case)):
                        self.assertEqual(quotient_root,
                                         test_case.quotient_root)
                        self.assertEqual(remainder, test_case.remainder)
                    yield Tick()
            sim.add_clock(2e-6)
            sim.add_sync_process(generate_process)
            sim.add_sync_process(check_process)
            sim.run()

    def test_bit_width_8_fract_width_4_radix_2(self):
        self.handle_case(DivPipeCoreConfig(bit_width=8,
                                           fract_width=4,
                                           log2_radix=1))

    # FIXME: add more test_* functions


if __name__ == '__main__':
    unittest.main()
