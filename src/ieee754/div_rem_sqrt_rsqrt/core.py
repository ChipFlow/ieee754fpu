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
from nmigen import (Elaboratable, Module, Signal, Const, Mux, Cat, Array)
from nmigen.lib.coding import PriorityEncoder
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
        print(f"{self}: n_stages={self.n_stages}")

    def __repr__(self):
        """ Get repr. """
        return f"DivPipeCoreConfig({self.bit_width}, " \
            + f"{self.fract_width}, {self.log2_radix})"

    @property
    def n_stages(self):
        """ Get the number of ``DivPipeCoreCalculateStage`` needed. """
        return (self.bit_width + self.log2_radix - 1) // self.log2_radix


class DivPipeCoreOperation(enum.Enum):
    """ Operation for ``DivPipeCore``.

    :attribute UDivRem: unsigned divide/remainder.
    :attribute SqrtRem: square-root/remainder.
    :attribute RSqrtRem: reciprocal-square-root/remainder.
    """

    UDivRem = 0
    SqrtRem = 1
    RSqrtRem = 2

    def __int__(self):
        """ Convert to int. """
        return self.value

    @classmethod
    def create_signal(cls, *, src_loc_at=0, **kwargs):
        """ Create a signal that can contain a ``DivPipeCoreOperation``. """
        return Signal(min=min(map(int, cls)),
                      max=max(map(int, cls)) + 2,
                      src_loc_at=(src_loc_at + 1),
                      decoder=lambda v: str(cls(v)),
                      **kwargs)


DP = DivPipeCoreOperation


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

    def __init__(self, core_config, reset_less=True):
        """ Create a ``DivPipeCoreInputData`` instance. """
        self.core_config = core_config
        bw = core_config.bit_width
        fw = core_config.fract_width
        self.dividend = Signal(bw + fw, reset_less=reset_less)
        self.divisor_radicand = Signal(bw, reset_less=reset_less)
        self.operation = DP.create_signal(reset_less=reset_less)

    def __iter__(self):
        """ Get member signals. """
        yield self.dividend
        yield self.divisor_radicand
        yield self.operation

    def eq(self, rhs):
        """ Assign member signals. """
        return [self.dividend.eq(rhs.dividend),
                self.divisor_radicand.eq(rhs.divisor_radicand),
                self.operation.eq(rhs.operation),
                ]


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

    def __init__(self, core_config, reset_less=True):
        """ Create a ``DivPipeCoreInterstageData`` instance. """
        self.core_config = core_config
        bw = core_config.bit_width
        self.divisor_radicand = Signal(bw, reset_less=reset_less)
        self.operation = DP.create_signal(reset_less=reset_less)
        self.quotient_root = Signal(bw, reset_less=reset_less)
        self.root_times_radicand = Signal(bw * 2, reset_less=reset_less)
        self.compare_lhs = Signal(bw * 3, reset_less=reset_less)
        self.compare_rhs = Signal(bw * 3, reset_less=reset_less)

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

    def __init__(self, core_config, reset_less=True):
        """ Create a ``DivPipeCoreOutputData`` instance. """
        self.core_config = core_config
        bw = core_config.bit_width
        self.quotient_root = Signal(bw, reset_less=reset_less)
        self.remainder = Signal(bw * 3, reset_less=reset_less)

    def __iter__(self):
        """ Get member signals. """
        yield self.quotient_root
        yield self.remainder
        return

    def eq(self, rhs):
        """ Assign member signals. """
        return [self.quotient_root.eq(rhs.quotient_root),
                self.remainder.eq(rhs.remainder)]


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
        comb = m.d.comb

        comb += self.o.divisor_radicand.eq(self.i.divisor_radicand)
        comb += self.o.quotient_root.eq(0)
        comb += self.o.root_times_radicand.eq(0)

        lhs = Signal(self.core_config.bit_width * 3, reset_less=True)
        fw = self.core_config.fract_width

        with m.Switch(self.i.operation):
            with m.Case(int(DP.UDivRem)):
                comb += lhs.eq(self.i.dividend << fw)
            with m.Case(int(DP.SqrtRem)):
                comb += lhs.eq(self.i.divisor_radicand << (fw * 2))
            with m.Case(int(DP.RSqrtRem)):
                comb += lhs.eq(1 << (fw * 3))

        comb += self.o.compare_lhs.eq(lhs)
        comb += self.o.compare_rhs.eq(0)
        comb += self.o.operation.eq(self.i.operation)

        return m


class Trial(Elaboratable):
    def __init__(self, core_config, trial_bits, current_shift, log2_radix):
        self.core_config = core_config
        self.trial_bits = trial_bits
        self.current_shift = current_shift
        self.log2_radix = log2_radix
        bw = core_config.bit_width
        self.divisor_radicand = Signal(bw, reset_less=True)
        self.quotient_root = Signal(bw, reset_less=True)
        self.root_times_radicand = Signal(bw * 2, reset_less=True)
        self.compare_rhs = Signal(bw * 3, reset_less=True)
        self.trial_compare_rhs = Signal(bw * 3, reset_less=True)
        self.operation = DP.create_signal(reset_less=True)

    def elaborate(self, platform):

        m = Module()
        comb = m.d.comb

        dr = self.divisor_radicand
        qr = self.quotient_root
        rr = self.root_times_radicand

        trial_bits_sig = Const(self.trial_bits, self.log2_radix)
        trial_bits_sqrd_sig = Const(self.trial_bits * self.trial_bits,
                                    self.log2_radix * 2)

        tblen = self.core_config.bit_width+self.log2_radix
        tblen2 = self.core_config.bit_width+self.log2_radix*2
        dr_times_trial_bits_sqrd = Signal(tblen2, reset_less=True)
        comb += dr_times_trial_bits_sqrd.eq(dr * trial_bits_sqrd_sig)

        with m.Switch(self.operation):
            # UDivRem
            with m.Case(int(DP.UDivRem)):
                dr_times_trial_bits = Signal(tblen, reset_less=True)
                comb += dr_times_trial_bits.eq(dr * trial_bits_sig)
                div_rhs = self.compare_rhs

                div_term1 = dr_times_trial_bits
                div_term1_shift = self.core_config.fract_width
                div_term1_shift += self.current_shift
                div_rhs += div_term1 << div_term1_shift

                comb += self.trial_compare_rhs.eq(div_rhs)

            # SqrtRem
            with m.Case(int(DP.SqrtRem)):
                qr_times_trial_bits = Signal((tblen+1)*2, reset_less=True)
                comb += qr_times_trial_bits.eq(qr * trial_bits_sig)
                sqrt_rhs = self.compare_rhs

                sqrt_term1 = qr_times_trial_bits
                sqrt_term1_shift = self.core_config.fract_width
                sqrt_term1_shift += self.current_shift + 1
                sqrt_rhs += sqrt_term1 << sqrt_term1_shift
                sqrt_term2 = trial_bits_sqrd_sig
                sqrt_term2_shift = self.core_config.fract_width
                sqrt_term2_shift += self.current_shift * 2
                sqrt_rhs += sqrt_term2 << sqrt_term2_shift

                comb += self.trial_compare_rhs.eq(sqrt_rhs)

            # RSqrtRem
            with m.Case(int(DP.RSqrtRem)):
                rr_times_trial_bits = Signal((tblen+1)*3, reset_less=True)
                comb += rr_times_trial_bits.eq(rr * trial_bits_sig)
                rsqrt_rhs = self.compare_rhs

                rsqrt_term1 = rr_times_trial_bits
                rsqrt_term1_shift = self.current_shift + 1
                rsqrt_rhs += rsqrt_term1 << rsqrt_term1_shift
                rsqrt_term2 = dr_times_trial_bits_sqrd
                rsqrt_term2_shift = self.current_shift * 2
                rsqrt_rhs += rsqrt_term2 << rsqrt_term2_shift

                comb += self.trial_compare_rhs.eq(rsqrt_rhs)

        return m


class DivPipeCoreCalculateStage(Elaboratable):
    """ Calculate Stage of the core of the div/rem/sqrt/rsqrt pipeline. """

    def __init__(self, core_config, stage_index):
        """ Create a ``DivPipeCoreSetupStage`` instance. """
        assert stage_index in range(core_config.n_stages)
        self.core_config = core_config
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
        comb = m.d.comb

        # copy invariant inputs to outputs (for next stage)
        comb += self.o.divisor_radicand.eq(self.i.divisor_radicand)
        comb += self.o.operation.eq(self.i.operation)
        comb += self.o.compare_lhs.eq(self.i.compare_lhs)

        # constants
        log2_radix = self.core_config.log2_radix
        current_shift = self.core_config.bit_width
        current_shift -= self.stage_index * log2_radix
        log2_radix = min(log2_radix, current_shift)
        assert log2_radix > 0
        current_shift -= log2_radix
        print(f"DivPipeCoreCalc: stage {self.stage_index}"
              + f" of {self.core_config.n_stages} handling "
              + f"bits [{current_shift}, {current_shift+log2_radix})"
              + f" of {self.core_config.bit_width}")
        radix = 1 << log2_radix

        # trials within this radix range.  carried out by Trial module,
        # results stored in pass_flags.  pass_flags are unary priority.
        trial_compare_rhs_values = []
        pfl = []
        for trial_bits in range(radix):
            t = Trial(self.core_config, trial_bits, current_shift, log2_radix)
            setattr(m.submodules, "trial%d" % trial_bits, t)

            comb += t.divisor_radicand.eq(self.i.divisor_radicand)
            comb += t.quotient_root.eq(self.i.quotient_root)
            comb += t.root_times_radicand.eq(self.i.root_times_radicand)
            comb += t.compare_rhs.eq(self.i.compare_rhs)
            comb += t.operation.eq(self.i.operation)

            # get the trial output
            trial_compare_rhs_values.append(t.trial_compare_rhs)

            # make the trial comparison against the [invariant] lhs.
            # trial_compare_rhs is always decreasing as trial_bits increases
            pass_flag = Signal(name=f"pass_flag_{trial_bits}", reset_less=True)
            comb += pass_flag.eq(self.i.compare_lhs >= t.trial_compare_rhs)
            pfl.append(pass_flag)

        # Cat all the pass flags list together (easier to handle, below)
        pass_flags = Signal(radix, reset_less=True)
        comb += pass_flags.eq(Cat(*pfl))

        # convert pass_flags (unary priority) to next_bits (binary index)
        #
        # Assumes that for each set bit in pass_flag, all previous bits are
        # also set.
        #
        # Assumes that pass_flag[0] is always set (since
        # compare_lhs >= compare_rhs is a pipeline invariant).

        m.submodules.pe = pe = PriorityEncoder(radix)
        next_bits = Signal(log2_radix, reset_less=True)
        comb += pe.i.eq(~pass_flags)
        with m.If(~pe.n):
            comb += next_bits.eq(pe.o-1)
        with m.Else():
            comb += next_bits.eq(radix-1)

        # get the highest passing rhs trial (indexed by next_bits)
        ta = Array(trial_compare_rhs_values)
        comb += self.o.compare_rhs.eq(ta[next_bits])

        # create outputs for next phase
        qr = self.i.quotient_root | (next_bits << current_shift)
        rr = self.i.root_times_radicand + ((self.i.divisor_radicand * next_bits)
                                                     << current_shift)
        comb += self.o.quotient_root.eq(qr)
        comb += self.o.root_times_radicand.eq(rr)

        return m


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
        m.submodules.div_pipe_core_final = self
        m.d.comb += self.i.eq(i)

    def process(self, i):
        """ Pipeline stage process. """
        return self.o  # return processed data (ignore i)

    def elaborate(self, platform):
        """ Elaborate into ``Module``. """
        m = Module()
        comb = m.d.comb

        comb += self.o.quotient_root.eq(self.i.quotient_root)
        comb += self.o.remainder.eq(self.i.compare_lhs - self.i.compare_rhs)

        return m
