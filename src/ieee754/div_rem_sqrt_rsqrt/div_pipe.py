# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information
""" div/rem/sqrt/rsqrt pipeline. """
from .core import (DivPipeCoreConfig, DivPipeCoreInputData,
                   DivPipeCoreInterstageData, DivPipeCoreOutputData)


class DivPipeBaseData:
    """ input data base type for ``DivPipe``.
    """

    def __init__(self, pspec):
        """ Create a ``DivPipeBaseData`` instance. """
        width = pspec['width']
        self.out_do_z = Signal(reset_less=True)
        self.oz = Signal(width, reset_less=True)

        self.ctx = FPPipeContext(pspec)  # context: muxid, operator etc.
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


class DivPipeInputData(DivPipeCoreInputData, DivPipeBaseData):
    """ input data type for ``DivPipe``.
    """

    def __init__(self, core_config):
        """ Create a ``DivPipeInputData`` instance. """
        DivPipeCoreInputData.__init__(self, core_config)
        DivPipeBaseData.__init__(self, pspec)  # XXX TODO args
        self.out_do_z = Signal(reset_less=True)
        self.oz = Signal(width, reset_less=True)

        self.ctx = FPPipeContext(pspec)  # context: muxid, operator etc.
        self.muxid = self.ctx.muxid             # annoying. complicated.

    def __iter__(self):
        """ Get member signals. """
        yield from DivPipeCoreInputData.__iter__(self)
        yield from DivPipeBaseData.__iter__(self)

    def eq(self, rhs):
        """ Assign member signals. """
        return DivPipeBaseData.eq(self, rhs) + \
            DivPipeCoreInputData.eq(self, rhs)


class DivPipeInterstageData(DivPipeCoreInterstageData, DivPipeBaseData):
    """ interstage data type for ``DivPipe``.

    :attribute core_config: ``DivPipeCoreConfig`` instance describing the
        configuration to be used.
    """

    def __init__(self, core_config):
        """ Create a ``DivPipeCoreInterstageData`` instance. """
        DivPipeCoreInterstageData.__init__(self, core_config)
        DivPipeBaseData.__init__(self, pspec)  # XXX TODO args

    def __iter__(self):
        """ Get member signals. """
        yield from DivPipeInterstageData.__iter__(self)
        yield from DivPipeBaseData.__iter__(self)

    def eq(self, rhs):
        """ Assign member signals. """
        return DivPipeBaseData.eq(self, rhs) + \
            DivPipeCoreInterstageData.eq(self, rhs)


class DivPipeOutputData(DivPipeCoreOutputData, DivPipeBaseData):
    """ interstage data type for ``DivPipe``.

    :attribute core_config: ``DivPipeCoreConfig`` instance describing the
        configuration to be used.
    """

    def __init__(self, core_config):
        """ Create a ``DivPipeCoreOutputData`` instance. """
        DivPipeCoreOutputData.__init__(self, core_config)
        DivPipeBaseData.__init__(self, pspec)  # XXX TODO args

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
