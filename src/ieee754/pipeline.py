# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

from abc import ABCMeta
from nmigen import Elaboratable

from nmutil.singlepipe import SimpleHandshake
import threading


class PipelineSpec:
    """ Pipeline Specification base class.

    :attribute width: the IEEE754 FP bitwidth
    :attribute id_wid: the Reservation Station muxid bitwidth
    :attribute op_wid: an "operand bitwidth" passed down all stages
    :attribute opkls: an optional class that is instantiated as the "operand"

    See ieee754/fpcommon/getop FPPipeContext for how (where) PipelineSpec
    is used.  FPPipeContext is passed down *every* stage of a pipeline
    and contains the Reservation Station multiplexer ID as well as
    an optional "operand".  This "operand" may be used to *change*
    the behaviour of the pipeline.  In RISC-V terminology it would
    typically be set to e.g. funct7 or parts thereof.

    """

    def __init__(self, width, id_width, op_wid=0, opkls=None, pipekls=None):
        """ Create a PipelineSpec. """
        self.width = width
        self.id_wid = id_width
        self.op_wid = op_wid
        self.opkls = opkls
        self.pipekls = pipekls or SimpleHandshakeRedir
        self.stage = None
        self.core_config = None
        self.fpformat = None
        self.n_comb_stages = None

# with many thanks to jsbueno on stackexchange for this one
# https://stackoverflow.com/questions/57273070/
# list post:
# http://lists.libre-riscv.org/pipermail/libre-riscv-dev/2019-July/002259.html

class Meta(ABCMeta):
    registry = {}
    recursing = threading.local()
    recursing.check = False
    mlock = threading.Lock()

    def __call__(cls, *args, **kw):
        mcls = cls.__class__
        if mcls.recursing.check:
            return super().__call__(*args, **kw)
        spec = args[0]
        base = spec.pipekls # pick up the dynamic class from PipelineSpec, HERE

        if (cls, base) not in mcls.registry:
            print ("__call__", args, kw, cls, base,
                   base.__bases__, cls.__bases__)
            mcls.registry[cls, base] = type(
                cls.__name__,
                (cls, base) + cls.__bases__[1:],
                {}
            )
        real_cls = mcls.registry[cls, base]

        with mcls.mlock:
            mcls.recursing.check = True
            instance = real_cls.__class__.__call__(real_cls, *args, **kw)
            mcls.recursing.check = False
        return instance


# Inherit from this class instead of SimpleHandshake (or other ControlBase
# derivative), and the metaclass will instead *replace* DynamicPipe -
# *at runtime* - with the class that is specified *as a parameter*
# in PipelineSpec.
#
# as explained in the list posting and in the stackexchange post, this is
# needed to avoid a MASSIVE suite of duplicated multiple-inheritance classes
# that "Mix in" SimpleHandshake (or other).
#
# unfortunately, composition does not work in this instance
# (make an *instance* of SimpleHandshake or other class and pass it in)
# due to the multiple level inheritance, and in several places
# the inheriting class needs to do some setup that the deriving class
# needs in order to function correctly.

class DynamicPipe(metaclass=Meta):
    def __init__(self, *args):
        print ("DynamicPipe init", super(), args)
        super().__init__(self, *args)


# bad hack: the DynamicPipe metaclass ends up creating an __init__ signature
# for the dynamically-derived class.  luckily, SimpleHandshake only needs
# "self" as the 1st argument (it is its own "Stage").  anything else
# could hypothetically be passed through the pspec.
class SimpleHandshakeRedir(SimpleHandshake):
    def __init__(self, mod, *args):
        print ("redir", mod, args)
        stage = self
        if args and args[0].stage:
            stage = args[0].stage
        SimpleHandshake.__init__(self, stage)

