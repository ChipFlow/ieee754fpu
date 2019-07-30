# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

from nmutil.singlepipe import SimpleHandshake


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
        self.pipekls = pipekls or SimpleHandshake
        self.core_config = None
        self.fpformat = None
        self.n_comb_stages = None


def DynamicPipeCreate(pspec, *args, **kwargs):
    superclass = pspec.pipekls
    class DynamicPipe(superclass):
        def __init__(self, *args, **kwargs):
            print(superclass)
            superclass.__init__(self, *args, **kwargs)
        pass
    return DynamicPipe(*args, **kwargs)

