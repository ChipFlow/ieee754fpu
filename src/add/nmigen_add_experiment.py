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
from fpcommon.getop import (FPGetOpMod, FPGetOp, FPNumBase2Ops, FPADDBaseData,
                            FPGet2OpMod, FPGet2Op)
from fpcommon.denorm import (FPSCData, FPAddDeNormMod, FPAddDeNorm)
from fpcommon.postcalc import FPAddStage1Data
from fpcommon.postnormalise import (FPNorm1Data, FPNorm1ModSingle,
                            FPNorm1ModMulti, FPNorm1Single, FPNorm1Multi)
from fpcommon.roundz import (FPRoundData, FPRoundMod, FPRound)
from fpcommon.corrections import (FPCorrectionsMod, FPCorrections)
from fpcommon.pack import (FPPackData, FPPackMod, FPPack)
from fpcommon.normtopack import FPNormToPack
from fpcommon.putz import (FPPutZ, FPPutZIdx)

from fpadd.specialcases import (FPAddSpecialCasesMod, FPAddSpecialCases,
                                FPAddSpecialCasesDeNorm)
from fpadd.align import (FPAddAlignMulti, FPAddAlignMultiMod, FPNumIn2Ops,
                         FPAddAlignSingleMod, FPAddAlignSingle)
from fpadd.add0 import (FPAddStage0Data, FPAddStage0Mod, FPAddStage0)
from fpadd.add1 import (FPAddStage1Mod, FPAddStage1)
from fpadd.addstages import FPAddAlignSingleAdd

from fpadd.statemachine import FPADDBase, FPADD
from fpadd.pipeline import FPADDMuxInOut

