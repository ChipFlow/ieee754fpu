# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information


class PipelineSpec:
    """ Pipeline Specification base class.

    :attribute width: FIXME: document
    :attribute id_wid: FIXME: document
    :attribute op_wid: FIXME: document
    """

    def __init__(self, width, id_width, opcode_width):
        """ Create a PipelineSpec. """
        self.width = width
        self.id_wid = id_width
        self.op_wid = opcode_width
        self.opkls = None
