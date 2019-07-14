# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information


class PipelineSpec:
    """ Pipeline Specification base class.

    :attribute width: FIXME: document
    :attribute id_width: FIXME: document
    :attribute opcode_width: FIXME: document
    """

    def __init__(self, width, id_width, opcode_width):
        """ Create a PipelineSpec. """
        self.width = width
        self.id_width = id_width
        self.opcode_width = opcode_width
