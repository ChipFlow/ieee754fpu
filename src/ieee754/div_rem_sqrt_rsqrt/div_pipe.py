# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information
""" div/rem/sqrt/rsqrt pipeline. """

from nmigen import Signal
from ieee754.div_rem_sqrt_rsqrt.core import (DivPipeCoreConfig,
                                             DivPipeCoreInputData,
                                             DivPipeCoreInterstageData,
                                             DivPipeCoreOutputData,
                                             DivPipeCoreSetupStage,
                                             DivPipeCoreCalculateStage,
                                             DivPipeCoreFinalStage,
                                             )
from ieee754.fpcommon.getop import FPPipeContext
from ieee754.fpcommon.fpbase import FPFormat, FPNumBaseRecord


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

    def __init__(self, pspec):
        """ Create a ``DivPipeBaseData`` instance. """
        self.pspec = pspec
        width = pspec.width
        # s and e carried: m ignored
        self.z = FPNumBaseRecord(width, False, name="z")
        self.out_do_z = Signal(reset_less=True)
        self.oz = Signal(width, reset_less=True)

        self.ctx = FPPipeContext(pspec)  # context: muxid, operator etc.
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
        return [self.z.eq(rhs.z), self.out_do_z.eq(rhs.out_do_z),
                self.oz.eq(rhs.oz), self.ctx.eq(rhs.ctx)]


class DivPipeInputData(DivPipeCoreInputData, DivPipeBaseData):
    """ input data type for ``DivPipe``. """

    def __init__(self, pspec):
        """ Create a ``DivPipeInputData`` instance. """
        DivPipeCoreInputData.__init__(self, pspec.core_config)
        DivPipeBaseData.__init__(self, pspec)

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

    def __init__(self, pspec):
        """ Create a ``DivPipeInterstageData`` instance. """
        DivPipeCoreInterstageData.__init__(self, pspec.core_config)
        DivPipeBaseData.__init__(self, pspec)

    def __iter__(self):
        """ Get member signals. """
        yield from DivPipeCoreInterstageData.__iter__(self)
        yield from DivPipeBaseData.__iter__(self)

    def eq(self, rhs):
        """ Assign member signals. """
        #print (self, rhs)
        return DivPipeCoreInterstageData.eq(self, rhs) + \
               DivPipeBaseData.eq(self, rhs)


class DivPipeOutputData(DivPipeCoreOutputData, DivPipeBaseData):
    """ output data type for ``DivPipe``. """

    def __init__(self, pspec):
        """ Create a ``DivPipeOutputData`` instance. """
        DivPipeCoreOutputData.__init__(self, pspec.core_config)
        DivPipeBaseData.__init__(self, pspec)

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
        m.d.comb += self.o.ctx.eq(self.i.ctx)
        m.d.comb += self.o.z.eq(self.i.z)
        m.d.comb += self.o.oz.eq(self.i.oz)
        m.d.comb += self.o.out_do_z.eq(self.i.out_do_z)


class DivPipeSetupStage(DivPipeBaseStage, DivPipeCoreSetupStage):
    """ FIXME: add docs. """

    def __init__(self, pspec):
        self.pspec = pspec
        #print ("DivPipeSetupStage", pspec, pspec.core_config)
        DivPipeCoreSetupStage.__init__(self, pspec.core_config)

    def ispec(self):
        """ Get the input spec for this pipeline stage."""
        return DivPipeInputData(self.pspec)

    def ospec(self):
        """ Get the output spec for this pipeline stage."""
        return DivPipeInterstageData(self.pspec)

    def elaborate(self, platform):
        # XXX TODO: out_do_z logic!
        m = DivPipeCoreSetupStage.elaborate(self, platform)
        self._elaborate(m, platform)
        return m


class DivPipeCalculateStage(DivPipeBaseStage, DivPipeCoreCalculateStage):
    """ FIXME: add docs. """

    def __init__(self, pspec, stage_idx):
        self.pspec = pspec
        DivPipeCoreCalculateStage.__init__(self, pspec.core_config, stage_idx)

    def ispec(self):
        """ Get the input spec for this pipeline stage."""
        return DivPipeInterstageData(self.pspec)

    def ospec(self):
        """ Get the output spec for this pipeline stage."""
        return DivPipeInterstageData(self.pspec)

    def elaborate(self, platform):
        # XXX TODO: out_do_z logic!
        m = DivPipeCoreCalculateStage.elaborate(self, platform)
        self._elaborate(m, platform)
        return m


class DivPipeFinalStage(DivPipeBaseStage, DivPipeCoreFinalStage):
    """ FIXME: add docs. """

    def __init__(self, pspec):
        self.pspec = pspec
        DivPipeCoreFinalStage.__init__(self, pspec.core_config)

    def ispec(self):
        """ Get the input spec for this pipeline stage."""
        return DivPipeInterstageData(self.pspec)

    def ospec(self):
        """ Get the output spec for this pipeline stage."""
        return DivPipeOutputData(self.pspec)

    def elaborate(self, platform):
        # XXX TODO: out_do_z logic!
        m = DivPipeCoreFinalStage.elaborate(self, platform)
        self._elaborate(m, platform)
        return m
