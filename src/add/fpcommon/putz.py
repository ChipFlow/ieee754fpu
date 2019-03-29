# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal, Cat, Mux, Array, Const
from nmigen.lib.coding import PriorityEncoder
from nmigen.cli import main, verilog
from math import log

from fpbase import FPNumIn, FPNumOut, FPOp, Overflow, FPBase, FPNumBase
from fpbase import MultiShiftRMerge, Trigger
from singlepipe import (ControlBase, StageChain, UnbufferedPipeline,
                        PassThroughStage)
from multipipe import CombMuxOutPipe
from multipipe import PriorityCombMuxInPipe

from fpbase import FPState, FPID
from fpcommon.getop import (FPGetOpMod, FPGetOp, FPNumBase2Ops, FPADDBaseData,                              FPGet2OpMod, FPGet2Op)
from fpcommon.denorm import (FPSCData, FPAddDeNormMod, FPAddDeNorm)
from fpcommon.postcalc import FPAddStage1Data
from fpcommon.postnormalise import (FPNorm1Data, FPNorm1ModSingle,
                            FPNorm1ModMulti, FPNorm1Single, FPNorm1Multi)
from fpcommon.roundz import (FPRoundData, FPRoundMod, FPRound)
from fpcommon.corrections import (FPCorrectionsMod, FPCorrections)
from fpcommon.pack import (FPPackData, FPPackMod, FPPack)
from fpcommon.normtopack import FPNormToPack


class FPPutZ(FPState):

    def __init__(self, state, in_z, out_z, in_mid, out_mid, to_state=None):
        FPState.__init__(self, state)
        if to_state is None:
            to_state = "get_ops"
        self.to_state = to_state
        self.in_z = in_z
        self.out_z = out_z
        self.in_mid = in_mid
        self.out_mid = out_mid

    def action(self, m):
        if self.in_mid is not None:
            m.d.sync += self.out_mid.eq(self.in_mid)
        m.d.sync += [
          self.out_z.z.v.eq(self.in_z)
        ]
        with m.If(self.out_z.z.stb & self.out_z.z.ack):
            m.d.sync += self.out_z.z.stb.eq(0)
            m.next = self.to_state
        with m.Else():
            m.d.sync += self.out_z.z.stb.eq(1)


class FPPutZIdx(FPState):

    def __init__(self, state, in_z, out_zs, in_mid, to_state=None):
        FPState.__init__(self, state)
        if to_state is None:
            to_state = "get_ops"
        self.to_state = to_state
        self.in_z = in_z
        self.out_zs = out_zs
        self.in_mid = in_mid

    def action(self, m):
        outz_stb = Signal(reset_less=True)
        outz_ack = Signal(reset_less=True)
        m.d.comb += [outz_stb.eq(self.out_zs[self.in_mid].stb),
                     outz_ack.eq(self.out_zs[self.in_mid].ack),
                    ]
        m.d.sync += [
          self.out_zs[self.in_mid].v.eq(self.in_z.v)
        ]
        with m.If(outz_stb & outz_ack):
            m.d.sync += self.out_zs[self.in_mid].stb.eq(0)
            m.next = self.to_state
        with m.Else():
            m.d.sync += self.out_zs[self.in_mid].stb.eq(1)

