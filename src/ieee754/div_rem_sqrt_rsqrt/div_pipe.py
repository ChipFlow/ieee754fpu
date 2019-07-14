# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information
""" div/rem/sqrt/rsqrt pipeline. """

from .core import (DivPipeCoreConfig, DivPipeCoreInputData,
                   DivPipeCoreInterstageData, DivPipeCoreOutputData)
from ieee754.fpcommon.getop import FPPipeContext


class DivPipeConfig:
    """ Configuration for the div/rem/sqrt/rsqrt pipeline.

    :attribute pspec: FIXME: document
    :attribute core_config: the ``DivPipeCoreConfig`` instance.
    """

    def __init__(self, pspec):
        """ Create a ``DivPipeConfig`` instance. """
        self.pspec = pspec
        # FIXME: get bit_width, fract_width, and log2_radix from pspec or pass
        # in as arguments
        self.core_config = DivPipeCoreConfig(bit_width,
                                             fract_width,
                                             log2_radix)


class DivPipeBaseData:
    """ input data base type for ``DivPipe``.

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
        self.out_do_z = Signal(reset_less=True)
        self.oz = Signal(width, reset_less=True)

        self.ctx = FPPipeContext(config.pspec)  # context: muxid, operator etc.
        # FIXME: add proper muxid explanation somewhere and refer to it here
        self.muxid = self.ctx.muxid  # annoying. complicated.

    def __iter__(self):
        """ Get member signals. """
        yield self.out_do_z
        yield self.oz
        yield from self.ctx

    def eq(self, rhs):
        """ Assign member signals. """
        return [self.out_do_z.eq(i.out_do_z), self.oz.eq(i.oz),
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
        m.d.comb += self.o.oz.eq(self.i.oz)
        m.d.comb += self.o.out_do_z.eq(self.i.out_do_z)
        m.d.comb += self.o.ctx.eq(self.i.ctx)

# FIXME: in DivPipeSetupStage.elaborate
# DivPipeBaseStage._elaborate(self, m, platform)

# FIXME: in DivPipeCalculateStage.elaborate
# DivPipeBaseStage._elaborate(self, m, platform)

# FIXME: in DivPipeFinalStage.elaborate
# DivPipeBaseStage._elaborate(self, m, platform)
