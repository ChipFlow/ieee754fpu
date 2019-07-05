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
from nmigen import (Elaboratable, Module, Signal, Const, Mux)
import enum

# TODO, move to new (suitable) location
#from ieee754.fpcommon.getop import FPPipeContext


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

    @property
    def num_calculate_stages(self):
        """ Get the number of ``DivPipeCoreCalculateStage`` needed. """
        return (self.bit_width + self.log2_radix - 1) // self.log2_radix


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


# TODO: move to suitable location
class DivPipeBaseData:
    """ input data base type for ``DivPipe``.
    """

    def __init__(self, width, pspec):
        """ Create a ``DivPipeBaseData`` instance. """
        self.out_do_z = Signal(reset_less=True)
        self.oz = Signal(width, reset_less=True)

        self.ctx = FPPipeContext(width, pspec)  # context: muxid, operator etc.
        self.muxid = self.ctx.muxid             # annoying. complicated.

    def __iter__(self):
        """ Get member signals. """
        yield self.out_do_z
        yield self.oz
        yield from self.ctx

    def eq(self, rhs):
        """ Assign member signals. """
        return [self.out_do_z.eq(i.out_do_z), self.oz.eq(i.oz),
                self.ctx.eq(i.ctx)]


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

        # FIXME: this goes into (is replaced by) self.ctx.op
        self.operation = DivPipeCoreOperation.create_signal(reset_less=True)

    def __iter__(self):
        """ Get member signals. """
        yield self.dividend
        yield self.divisor_radicand
        yield self.operation  # FIXME: delete.  already covered by self.ctx
        return
        yield self.z
        yield self.out_do_z
        yield self.oz
        yield from self.ctx

    def eq(self, rhs):
        """ Assign member signals. """
        return [self.dividend.eq(rhs.dividend),
                self.divisor_radicand.eq(rhs.divisor_radicand),
                self.operation.eq(rhs.operation)]  # FIXME: delete.


# TODO: move to suitable location
class DivPipeInputData(DivPipeCoreInputData, DivPipeBaseData):
    """ input data type for ``DivPipe``.
    """

    def __init__(self, core_config):
        """ Create a ``DivPipeInputData`` instance. """
        DivPipeCoreInputData.__init__(self, core_config)
        DivPipeBaseData.__init__(self, width, pspec) # XXX TODO args
        self.out_do_z = Signal(reset_less=True)
        self.oz = Signal(width, reset_less=True)

        self.ctx = FPPipeContext(width, pspec)  # context: muxid, operator etc.
        self.muxid = self.ctx.muxid             # annoying. complicated.

    def __iter__(self):
        """ Get member signals. """
        yield from DivPipeCoreInputData.__iter__(self)
        yield from DivPipeBaseData.__iter__(self)

    def eq(self, rhs):
        """ Assign member signals. """
        return DivPipeBaseData.eq(self, rhs) + \
               DivPipeCoreInputData.eq(self, rhs)



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
        # XXX FIXME: delete.  already covered by self.ctx.op
        self.operation = DivPipeCoreOperation.create_signal(reset_less=True)
        self.quotient_root = Signal(core_config.bit_width, reset_less=True)
        self.root_times_radicand = Signal(core_config.bit_width * 2,
                                          reset_less=True)
        self.compare_lhs = Signal(core_config.bit_width * 3, reset_less=True)
        self.compare_rhs = Signal(core_config.bit_width * 3, reset_less=True)

    def __iter__(self):
        """ Get member signals. """
        yield self.divisor_radicand
        yield self.operation  # XXX FIXME: delete.  already in self.ctx.op
        yield self.quotient_root
        yield self.root_times_radicand
        yield self.compare_lhs
        yield self.compare_rhs

    def eq(self, rhs):
        """ Assign member signals. """
        return [self.divisor_radicand.eq(rhs.divisor_radicand),
                self.operation.eq(rhs.operation),  # FIXME: delete.
                self.quotient_root.eq(rhs.quotient_root),
                self.root_times_radicand.eq(rhs.root_times_radicand),
                self.compare_lhs.eq(rhs.compare_lhs),
                self.compare_rhs.eq(rhs.compare_rhs)]


# TODO: move to suitable location
class DivPipeInterstageData(DivPipeCoreInterstageData, DivPipeBaseData):
    """ interstage data type for ``DivPipe``.

    :attribute core_config: ``DivPipeCoreConfig`` instance describing the
        configuration to be used.
    """

    def __init__(self, core_config):
        """ Create a ``DivPipeCoreInterstageData`` instance. """
        DivPipeCoreInterstageData.__init__(self, core_config)
        DivPipeBaseData.__init__(self, width, pspec) # XXX TODO args

    def __iter__(self):
        """ Get member signals. """
        yield from DivPipeInterstageData.__iter__(self)
        yield from DivPipeBaseData.__iter__(self)

    def eq(self, rhs):
        """ Assign member signals. """
        return DivPipeBaseData.eq(self, rhs) + \
               DivPipeCoreInterstageData.eq(self, rhs)


class DivPipeCoreOutputData:
    """ output data type for ``DivPipeCore``.

    :attribute core_config: ``DivPipeCoreConfig`` instance describing the
        configuration to be used.
    :attribute quotient_root: the quotient or root part of the result of the
        operation. Signal with a bit-width of ``core_config.bit_width`` and a
        fract-width of ``core_config.fract_width`` bits.
    :attribute remainder: the remainder part of the result of the operation.
        Signal with a bit-width of ``core_config.bit_width * 3`` and a
        fract-width of ``core_config.fract_width * 3`` bits.
    """

    def __init__(self, core_config):
        """ Create a ``DivPipeCoreOutputData`` instance. """
        self.core_config = core_config
        self.quotient_root = Signal(core_config.bit_width, reset_less=True)
        self.remainder = Signal(core_config.bit_width * 3, reset_less=True)

    def __iter__(self):
        """ Get member signals. """
        yield self.quotient_root
        yield self.remainder
        return

    def eq(self, rhs):
        """ Assign member signals. """
        return [self.quotient_root.eq(rhs.quotient_root),
                self.remainder.eq(rhs.remainder)]


# TODO: move to suitable location
class DivPipeOutputData(DivPipeCoreOutputData, DivPipeBaseData):
    """ interstage data type for ``DivPipe``.

    :attribute core_config: ``DivPipeCoreConfig`` instance describing the
        configuration to be used.
    """

    def __init__(self, core_config):
        """ Create a ``DivPipeCoreOutputData`` instance. """
        DivPipeCoreOutputData.__init__(self, core_config)
        DivPipeBaseData.__init__(self, width, pspec) # XXX TODO args

    def __iter__(self):
        """ Get member signals. """
        yield from DivPipeOutputData.__iter__(self)
        yield from DivPipeBaseData.__iter__(self)

    def eq(self, rhs):
        """ Assign member signals. """
        return DivPipeBaseData.eq(self, rhs) + \
               DivPipeCoreOutputData.eq(self, rhs)


class DivPipeBaseStage:
    """ Base Mix-in for DivPipe*Stage """

    def _elaborate(self, m, platform):
        m.d.comb += self.o.oz.eq(self.i.oz)
        m.d.comb += self.o.out_do_z.eq(self.i.out_do_z)
        m.d.comb += self.o.ctx.eq(self.i.ctx)


class DivPipeCoreSetupStage(Elaboratable):
    """ Setup Stage of the core of the div/rem/sqrt/rsqrt pipeline. """

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

        # XXX in DivPipeSetupStage
        DivPipeBaseStage._elaborate(self, m, platform)


class DivPipeCoreCalculateStage(Elaboratable):
    """ Calculate Stage of the core of the div/rem/sqrt/rsqrt pipeline. """

    def __init__(self, core_config, stage_index):
        """ Create a ``DivPipeCoreSetupStage`` instance. """
        self.core_config = core_config
        assert stage_index in range(core_config.num_calculate_stages)
        self.stage_index = stage_index
        self.i = self.ispec()
        self.o = self.ospec()

    def ispec(self):
        """ Get the input spec for this pipeline stage. """
        return DivPipeCoreInterstageData(self.core_config)

    def ospec(self):
        """ Get the output spec for this pipeline stage. """
        return DivPipeCoreInterstageData(self.core_config)

    def setup(self, m, i):
        """ Pipeline stage setup. """
        setattr(m.submodules,
                f"div_pipe_core_calculate_{self.stage_index}",
                self)
        m.d.comb += self.i.eq(i)

    def process(self, i):
        """ Pipeline stage process. """
        return self.o

    def elaborate(self, platform):
        """ Elaborate into ``Module``. """
        m = Module()
        m.d.comb += self.o.divisor_radicand.eq(self.i.divisor_radicand)
        m.d.comb += self.o.operation.eq(self.i.operation)
        m.d.comb += self.o.compare_lhs.eq(self.i.compare_lhs)
        log2_radix = self.core_config.log2_radix
        current_shift = self.core_config.bit_width
        current_shift -= self.stage_index * log2_radix
        log2_radix = min(log2_radix, current_shift)
        assert log2_radix > 0
        current_shift -= log2_radix
        radix = 1 << log2_radix
        trial_compare_rhs_values = []
        pass_flags = []
        for trial_bits in range(radix):
            shifted_trial_bits = Const(trial_bits, log2_radix) << current_shift
            shifted_trial_bits_sqrd = shifted_trial_bits * shifted_trial_bits

            # UDivRem
            div_rhs = self.i.compare_rhs
            div_factor1 = self.i.divisor_radicand * shifted_trial_bits
            div_rhs += div_factor1 << self.core_config.fract_width

            # SqrtRem
            sqrt_rhs = self.i.compare_rhs
            sqrt_factor1 = self.i.quotient_root * (shifted_trial_bits << 1)
            sqrt_rhs += sqrt_factor1 << self.core_config.fract_width
            sqrt_factor2 = shifted_trial_bits_sqrd
            sqrt_rhs += sqrt_factor2 << self.core_config.fract_width

            # RSqrtRem
            rsqrt_rhs = self.i.compare_rhs
            rsqrt_rhs += self.i.root_times_radicand * (shifted_trial_bits << 1)
            rsqrt_rhs += self.i.divisor_radicand * shifted_trial_bits_sqrd

            trial_compare_rhs = self.o.compare_rhs.like(
                name=f"trial_compare_rhs_{trial_bits}")

            with m.If(self.i.operation == DivPipeCoreOperation.UDivRem):
                m.d.comb += trial_compare_rhs.eq(div_rhs)
            with m.Elif(self.i.operation == DivPipeCoreOperation.SqrtRem):
                m.d.comb += trial_compare_rhs.eq(sqrt_rhs)
            with m.Else():  # DivPipeCoreOperation.RSqrtRem
                m.d.comb += trial_compare_rhs.eq(rsqrt_rhs)
            trial_compare_rhs_values.append(trial_compare_rhs)

            pass_flag = Signal(name=f"pass_flag_{trial_bits}")
            m.d.comb += pass_flag.eq(self.i.compare_lhs >= trial_compare_rhs)
            pass_flags.append(pass_flag)

        # convert pass_flags to next_bits.
        #
        # Assumes that for each set bit in pass_flag, all previous bits are
        # also set.
        #
        # Assumes that pass_flag[0] is always set (since
        # compare_lhs >= compare_rhs is a pipeline invariant).

        next_bits = Signal(log2_radix)
        for i in range(log2_radix):
            bit_value = 1
            for j in range(0, radix, 1 << i):
                bit_value ^= pass_flags[j]
            m.d.comb += next_bits.part(i, 1).eq(bit_value)

        next_compare_rhs = 0
        for i in range(radix):
            next_flag = pass_flags[i + 1] if i + 1 < radix else 0
            next_compare_rhs |= Mux(pass_flags[i] & ~next_flag,
                                    trial_compare_rhs_values[i],
                                    0)

        m.d.comb += self.o.compare_rhs.eq(next_compare_rhs)
        m.d.comb += self.o.root_times_radicand.eq(self.i.root_times_radicand
                                                  + ((self.i.divisor_radicand
                                                      * next_bits)
                                                     << current_shift))
        m.d.comb += self.o.quotient_root.eq(self.i.quotient_root
                                            | (next_bits << current_shift))
        return m

        # XXX in DivPipeCalculateStage
        DivPipeBaseStage._elaborate(self, m, platform)



class DivPipeCoreFinalStage(Elaboratable):
    """ Final Stage of the core of the div/rem/sqrt/rsqrt pipeline. """

    def __init__(self, core_config):
        """ Create a ``DivPipeCoreFinalStage`` instance."""
        self.core_config = core_config
        self.i = self.ispec()
        self.o = self.ospec()

    def ispec(self):
        """ Get the input spec for this pipeline stage."""
        return DivPipeCoreInterstageData(self.core_config)

    def ospec(self):
        """ Get the output spec for this pipeline stage."""
        return DivPipeCoreOutputData(self.core_config)

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

        m.d.comb += self.o.quotient_root.eq(self.i.quotient_root)
        m.d.comb += self.o.remainder.eq(self.i.compare_lhs
                                        - self.i.compare_rhs)

        return m

        # XXX in DivPipeFinalStage
        DivPipeBaseStage._elaborate(self, m, platform)

