from nmigen import Signal, Const
from nmutil.dynamicpipe import SimpleHandshakeRedir
from ieee754.fpcommon.fpbase import FPNumBaseRecord
from ieee754.pipeline import PipelineSpec
from nmutil.concurrentunit import num_bits
import math

from ieee754.cordic.pipe_data import (CordicData, CordicInitialData,
                                      CordicPipeSpec)


class FPCordicPipeSpec(CordicPipeSpec, PipelineSpec):
    def __init__(self, width, rounds_per_stage, num_rows):
        rec = FPNumBaseRecord(width, False)
        fracbits = 2 * rec.m_width
        self.width = width
        id_wid = num_bits(num_rows)
        CordicPipeSpec.__init__(self, fracbits, rounds_per_stage)
        PipelineSpec.__init__(self, width, op_wid=1, n_ops=1,
                              id_width=id_wid)
