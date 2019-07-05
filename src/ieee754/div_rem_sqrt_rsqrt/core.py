# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information
""" Core of the div/rem/sqrt/rsqrt pipeline.

Special case handling, input/output conversion, and muxid handling are handled
outside of these classes.

Algorithms based on ``algorithm.FixedUDivRemSqrtRSqrt``.

Formulas solved are:
* div/rem:
    ``dividend == quotient_root * divisor_radicand``
* sqrt/rem:
    ``divisor_radicand == quotient_root * quotient_root``
* rsqrt/rem:
    ``1 == quotient_root * quotient_root * divisor_radicand``

The remainder is the left-hand-side of the comparison minus the
right-hand-side of the comparison in the above formulas.
"""
from nmigen import (Elaboratable, Module, Signal)
import enum


class DivPipeCoreConfig:
    """ Configuration for core of the div/rem/sqrt/rsqrt pipeline.

    :attribute bit_width: base bit-width.
    :attribute fract_width: base fract-width. Specifies location of base-2
        radix point.
    :attribute log2_radix: number of bits of ``quotient_root`` that should be
        computed per pipeline stage.
    """

    def __init__(self, bit_width, fract_width, log2_radix):
        """ Create a ``DivPipeCoreConfig`` instance. """
        self.bit_width = bit_width
        self.fract_width = fract_width
        self.log2_radix = log2_radix

    def __repr__(self):
        """ Get repr. """
        return f"DivPipeCoreConfig({self.bit_width}, " \
            + f"{self.fract_width}, {self.log2_radix})"


class DivPipeCoreOperation(enum.IntEnum):
    """ Operation for ``DivPipeCore``.

    :attribute UDivRem: unsigned divide/remainder.
    :attribute SqrtRem: square-root/remainder.
    :attribute RSqrtRem: reciprocal-square-root/remainder.
    """

    UDivRem = 0
    SqrtRem = 1
    RSqrtRem = 2

    @classmethod
    def create_signal(cls, *, src_loc_at=0, **kwargs):
        """ Create a signal that can contain a ``DivPipeCoreOperation``. """
        return Signal(min=int(min(cls)),
                      max=int(max(cls)),
                      src_loc_at=(src_loc_at + 1),
                      decoder=cls,
                      **kwargs)


class DivPipeCoreInputData:
    """ input data type for ``DivPipeCore``.

    :attribute core_config: ``DivPipeCoreConfig`` instance describing the
        configuration to be used.
    :attribute dividend: dividend for div/rem. Signal with a bit-width of
        ``core_config.bit_width + core_config.fract_width`` and a fract-width
        of ``core_config.fract_width * 2`` bits.
    :attribute divisor_radicand: divisor for div/rem and radicand for
        sqrt/rsqrt. Signal with a bit-width of ``core_config.bit_width`` and a
        fract-width of ``core_config.fract_width`` bits.
    :attribute operation: the ``DivPipeCoreOperation`` to be computed.
    """

    def __init__(self, core_config):
        """ Create a ``DivPipeCoreInputData`` instance. """
        self.core_config = core_config
        self.dividend = Signal(core_config.bit_width + core_config.fract_width,
                               reset_less=True)
        self.divisor_radicand = Signal(core_config.bit_width, reset_less=True)
        self.operation = DivPipeCoreOperation.create_signal(reset_less=True)

    def __iter__(self):
        """ Get member signals. """
        yield self.dividend
        yield self.divisor_radicand
        yield self.operation

    def eq(self, rhs):
        """ Assign member signals. """
        return [self.dividend.eq(rhs.dividend),
                self.divisor_radicand.eq(rhs.divisor_radicand),
                self.operation.eq(rhs.operation)]


class DivPipeCoreInterstageData:
    """ interstage data type for ``DivPipeCore``.

    :attribute core_config: ``DivPipeCoreConfig`` instance describing the
        configuration to be used.
    :attribute divisor_radicand: divisor for div/rem and radicand for
        sqrt/rsqrt. Signal with a bit-width of ``core_config.bit_width`` and a
        fract-width of ``core_config.fract_width`` bits.
    :attribute operation: the ``DivPipeCoreOperation`` to be computed.
    :attribute quotient_root: the quotient or root part of the result of the
        operation. Signal with a bit-width of ``core_config.bit_width`` and a
        fract-width of ``core_config.fract_width`` bits.
    :attribute root_times_radicand: ``quotient_root * divisor_radicand``.
        Signal with a bit-width of ``core_config.bit_width * 2`` and a
        fract-width of ``core_config.fract_width * 2`` bits.
    :attribute compare_lhs: The left-hand-side of the comparison in the
        equation to be solved. Signal with a bit-width of
        ``core_config.bit_width * 3`` and a fract-width of
        ``core_config.fract_width * 3`` bits.
    :attribute compare_rhs: The right-hand-side of the comparison in the
        equation to be solved. Signal with a bit-width of
        ``core_config.bit_width * 3`` and a fract-width of
        ``core_config.fract_width * 3`` bits.
    """

    def __init__(self, core_config):
        """ Create a ``DivPipeCoreInterstageData`` instance. """
        self.core_config = core_config
        self.divisor_radicand = Signal(core_config.bit_width, reset_less=True)
        self.operation = DivPipeCoreOperation.create_signal(reset_less=True)
        self.quotient_root = Signal(core_config.bit_width, reset_less=True)
        self.root_times_radicand = Signal(core_config.bit_width * 2,
                                          reset_less=True)
        self.compare_lhs = Signal(core_config.bit_width * 3, reset_less=True)
        self.compare_rhs = Signal(core_config.bit_width * 3, reset_less=True)

    def __iter__(self):
        """ Get member signals. """
        yield self.divisor_radicand
        yield self.operation
        yield self.quotient_root
        yield self.root_times_radicand
        yield self.compare_lhs
        yield self.compare_rhs

    def eq(self, rhs):
        """ Assign member signals. """
        return [self.divisor_radicand.eq(rhs.divisor_radicand),
                self.operation.eq(rhs.operation),
                self.quotient_root.eq(rhs.quotient_root),
                self.root_times_radicand.eq(rhs.root_times_radicand),
                self.compare_lhs.eq(rhs.compare_lhs),
                self.compare_rhs.eq(rhs.compare_rhs)]


class DivPipeCoreSetupStage(Elaboratable):
    """ Setup Stage of the core of the div/rem/sqrt/rsqrt pipeline.
    """

    def __init__(self, core_config):
        """ Create a ``DivPipeCoreSetupStage`` instance."""
        self.core_config = core_config
        self.i = self.ispec()
        self.o = self.ospec()

    def ispec(self):
        """ Get the input spec for this pipeline stage."""
        return DivPipeCoreInputData(self.core_config)

    def ospec(self):
        """ Get the output spec for this pipeline stage."""
        return DivPipeCoreInterstageData(self.core_config)

    def setup(self, m, i):
        """ Pipeline stage setup. """
        m.submodules.div_pipe_core_setup = self
        m.d.comb += self.i.eq(i)

    def process(self, i):
        """ Pipeline stage process. """
        return self.o  # return processed data (ignore i)

    def elaborate(self, platform):
        """ Elaborate into ``Module``. """
        m = Module()

        m.d.comb += self.o.divisor_radicand.eq(self.i.divisor_radicand)
        m.d.comb += self.o.quotient_root.eq(0)
        m.d.comb += self.o.root_times_radicand.eq(0)

        with m.If(self.i.operation == DivPipeCoreOperation.UDivRem):
            m.d.comb += self.o.compare_lhs.eq(self.i.dividend
                                              << self.core_config.fract_width)
        with m.Elif(self.i.operation == DivPipeCoreOperation.SqrtRem):
            m.d.comb += self.o.compare_lhs.eq(
                self.i.divisor_radicand << (self.core_config.fract_width * 2))
        with m.Else():  # DivPipeCoreOperation.RSqrtRem
            m.d.comb += self.o.compare_lhs.eq(
                1 << (self.core_config.fract_width * 3))

        m.d.comb += self.o.compare_rhs.eq(0)
        m.d.comb += self.o.operation.eq(self.i.operation)

        return m
