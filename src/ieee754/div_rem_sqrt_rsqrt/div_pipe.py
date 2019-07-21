# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information
""" div/rem/sqrt/rsqrt pipeline. """

from .core import (DivPipeCoreConfig, DivPipeCoreInputData,
                   DivPipeCoreInterstageData, DivPipeCoreOutputData)
from ieee754.fpcommon.getop import FPPipeContext
from ieee754.fpcommon.fpbase import FPFormat, FPNumBaseRecord


class DivPipeConfig:
    """ Configuration for the div/rem/sqrt/rsqrt pipeline.

    :attribute pspec: ``PipelineSpec`` instance
    :attribute core_config: the ``DivPipeCoreConfig`` instance.
    """

    def __init__(self, pspec, log2_radix=3):
        """ Create a ``DivPipeConfig`` instance. """
        self.pspec = pspec
        bit_width = pspec.width
        fract_width = FPFormat.standard(bit_width).fraction_width
        self.core_config = DivPipeCoreConfig(bit_width,
                                             fract_width,
                                             log2_radix)


class DivPipeBaseData:
    """ input data base type for ``DivPipe``.

    :attribute z: a convenient way to carry the sign and exponent through
                  the pipeline from when they were computed right at the
                  start.
    :attribute out_do_z: FIXME: document
    :attribute oz: FIXME: document
    :attribute ctx: FIXME: document
    :attribute muxid:
        FIXME: document
        Alias of ``ctx.muxid``.
    :attribute config: the ``DivPipeConfig`` instance.
    """

    def __init__(self, config):
        """ Create a ``DivPipeBaseData`` instance. """
        self.config = config
        width = config.pspec.width
        self.z = FPNumBaseRecord(width, False) # s and e carried: m ignored
        self.out_do_z = Signal(reset_less=True)
        self.oz = Signal(width, reset_less=True)

        self.ctx = FPPipeContext(config.pspec)  # context: muxid, operator etc.
        # FIXME: add proper muxid explanation somewhere and refer to it here
        self.muxid = self.ctx.muxid  # annoying. complicated.

    def __iter__(self):
        """ Get member signals. """
        yield from self.z
        yield self.out_do_z
        yield self.oz
        yield from self.ctx

    def eq(self, rhs):
        """ Assign member signals. """
        return [self.z.eq(rhz.z, self.out_do_z.eq(i.out_do_z), self.oz.eq(i.oz),
                self.ctx.eq(i.ctx)]


class DivPipeInputData(DivPipeCoreInputData, DivPipeBaseData):
    """ input data type for ``DivPipe``. """

    def __init__(self, config):
        """ Create a ``DivPipeInputData`` instance. """
        DivPipeCoreInputData.__init__(self, config.core_config)
        DivPipeBaseData.__init__(self, config)

    def __iter__(self):
        """ Get member signals. """
        yield from DivPipeCoreInputData.__iter__(self)
        yield from DivPipeBaseData.__iter__(self)

    def eq(self, rhs):
        """ Assign member signals. """
        return DivPipeCoreInputData.eq(self, rhs) + \
            DivPipeBaseData.eq(self, rhs)


class DivPipeInterstageData(DivPipeCoreInterstageData, DivPipeBaseData):
    """ interstage data type for ``DivPipe``. """

    def __init__(self, config):
        """ Create a ``DivPipeInterstageData`` instance. """
        DivPipeCoreInterstageData.__init__(self, config.core_config)
        DivPipeBaseData.__init__(self, config)

    def __iter__(self):
        """ Get member signals. """
        yield from DivPipeCoreInterstageData.__iter__(self)
        yield from DivPipeBaseData.__iter__(self)

    def eq(self, rhs):
        """ Assign member signals. """
        return DivPipeCoreInterstageData.eq(self, rhs) + \
            DivPipeBaseData.eq(self, rhs)


class DivPipeOutputData(DivPipeCoreOutputData, DivPipeBaseData):
    """ output data type for ``DivPipe``. """

    def __init__(self, config):
        """ Create a ``DivPipeOutputData`` instance. """
        DivPipeCoreOutputData.__init__(self, config.core_config)
        DivPipeBaseData.__init__(self, config)

    def __iter__(self):
        """ Get member signals. """
        yield from DivPipeCoreOutputData.__iter__(self)
        yield from DivPipeBaseData.__iter__(self)

    def eq(self, rhs):
        """ Assign member signals. """
        return DivPipeCoreOutputData.eq(self, rhs) + \
            DivPipeBaseData.eq(self, rhs)


class DivPipeBaseStage:
    """ Base Mix-in for DivPipe*Stage. """

    def _elaborate(self, m, platform):
        m.d.comb += self.o.z.eq(self.i.z)
        m.d.comb += self.o.oz.eq(self.i.oz)
        m.d.comb += self.o.out_do_z.eq(self.i.out_do_z)
        m.d.comb += self.o.ctx.eq(self.i.ctx)

    def get_core_config(self):
        m_width = self.pspec.m_width # mantissa width
        # 4 extra bits on the mantissa: MSB is zero, MSB-1 is 1
        # then there is guard and round at the LSB end
        return DivPipeCoreConfig(m_width+4, 0, log_radix=2)


class DivPipeSetupStage(DivPipeBaseStage, DivPipeCoreSetupStage):

    def __init__(self, pspec):
        DivPipeCoreSetupStage.__init__(self.get_core_config())
        self.pspec = pspec

    def elaborate(self, platform):
        m = DivPipeCoreSetupStage(platform) # XXX TODO: out_do_z logic!
        self._elaborate(m, platform)
        return m


class DivPipeCalculateStage(DivPipeBaseStage, DivPipeCoreCalculateStage):

    def __init__(self, pspec, stage_index):
        DivPipeCoreCalculateStage.__init__(self.get_core_config(), stage_index)
        self.pspec = pspec

    def elaborate(self, platform):
        m = DivPipeCoreCalculateStage(platform) # XXX TODO: out_do_z logic!
        self._elaborate(m, platform)
        return m


class DivPipeFinalStage(DivPipeBaseStage, DivPipeCoreFinalStage):

    def __init__(self, pspec, stage_index):
        DivPipeCoreFinalStage.__init__(self.get_core_config(), stage_index)
        self.pspec = pspec

    def elaborate(self, platform):
        m = DivPipeCoreCalculateStage(platform) # XXX TODO: out_do_z logic!
        self._elaborate(m, platform)
        return m

