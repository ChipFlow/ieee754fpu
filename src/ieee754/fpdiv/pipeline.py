"""IEEE Floating Point Divider Pipeline

Relevant bugreport: http://bugs.libre-riscv.org/show_bug.cgi?id=99

Stack looks like this:

scnorm   - FPDIVSpecialCasesDeNorm ispec FPADDBaseData
------                             ospec FPSCData

                StageChain: FPDIVSpecialCasesMod,
                            FPAddDeNormMod

pipediv0 - FPDivStagesSetup        ispec FPSCData
--------                           ospec DivPipeInterstageData

                StageChain: FPDivStage0Mod,
                            DivPipeSetupStage,
                            DivPipeCalculateStage,
                            ...
                            DivPipeCalculateStage

pipediv1 - FPDivStagesIntermediate ispec DivPipeInterstageData
--------                           ospec DivPipeInterstageData

                StageChain: DivPipeCalculateStage,
                            ...
                            DivPipeCalculateStage
...
...

pipediv5 - FPDivStageFinal         ispec FPDivStage0Data
--------                           ospec FPAddStage1Data

                StageChain: DivPipeCalculateStage,
                            ...
                            DivPipeCalculateStage,
                            DivPipeFinalStage,
                            FPDivStage2Mod

normpack - FPNormToPack            ispec FPAddStage1Data
--------                           ospec FPPackData

                StageChain: Norm1ModSingle,
                            RoundMod,
                            CorrectionsMod,
                            PackMod

the number of combinatorial StageChains (n_comb_stages) in
FPDivStages is an argument arranged to get the length of the whole
pipeline down to sane numbers.

the reason for keeping the number of stages down is that for every
pipeline clock delay, a corresponding ReservationStation is needed.
if there are 24 pipeline stages, we need a whopping TWENTY FOUR
RS's.  that's far too many.  6 is just about an acceptable number.
even 8 is starting to get alarmingly high.
"""

from nmigen import Module
from nmigen.cli import main, verilog

from nmutil.singlepipe import ControlBase
from nmutil.concurrentunit import ReservationStations, num_bits

from ieee754.fpcommon.getop import FPADDBaseData
from ieee754.fpcommon.denorm import FPSCData
from ieee754.fpcommon.fpbase import FPFormat
from ieee754.fpcommon.pack import FPPackData
from ieee754.fpcommon.normtopack import FPNormToPack
from ieee754.fpdiv.specialcases import FPDIVSpecialCasesDeNorm
from ieee754.fpdiv.divstages import (FPDivStagesSetup,
                                     FPDivStagesIntermediate,
                                     FPDivStagesFinal)
from ieee754.pipeline import PipelineSpec
from ieee754.div_rem_sqrt_rsqrt.core import DivPipeCoreConfig


class FPDIVBasePipe(ControlBase):
    def __init__(self, pspec):
        self.pspec = pspec
        ControlBase.__init__(self)

        pipechain = []
        max_n_comb_stages = 3  # TODO (depends on how many RS's we want)
        # to which the answer: "as few as possible"
        # is required.  too many ReservationStations
        # means "big problems".

        # XXX BUG - subtracting 4 from number of stages stops assert
        # probably related to having to add 4 in FPDivMuxInOut
        radix = pspec.log2_radix
        n_stages = pspec.core_config.n_stages // max_n_comb_stages
        stage_idx = 0

        for i in range(n_stages):

            n_comb_stages = max_n_comb_stages
            # needs to convert input from pipestart ospec
            if i == 0:
                kls = FPDivStagesSetup
                #n_comb_stages -= 1  # reduce due to work done at start?

            # needs to convert output to pipeend ispec
            elif i == n_stages - 1:
                kls = FPDivStagesFinal
                #n_comb_stages -= 1  # FIXME - reduce due to work done at end?

            # intermediary stage
            else:
                kls = FPDivStagesIntermediate

            pipechain.append(kls(self.pspec, n_comb_stages, stage_idx))
            stage_idx += n_comb_stages # increment so that each CalcStage
                                       # gets a (correct) unique index

        self.pipechain = pipechain

        # start and end: unpack/specialcases then normalisation/packing
        self.pipestart = pipestart = FPDIVSpecialCasesDeNorm(self.pspec)
        self.pipeend = pipeend = FPNormToPack(self.pspec)

        self._eqs = self.connect([pipestart] + pipechain + [pipeend])

    def elaborate(self, platform):
        m = ControlBase.elaborate(self, platform)

        # add submodules
        m.submodules.scnorm = self.pipestart
        for i, p in enumerate(self.pipechain):
            setattr(m.submodules, "pipediv%d" % i, p)
        m.submodules.normpack = self.pipeend

        # ControlBase.connect creates the "eqs" needed to connect each pipe
        m.d.comb += self._eqs

        return m

def roundup(x, mod):
    return x if x % mod == 0 else x + mod - x % mod


class FPDIVMuxInOut(ReservationStations):
    """ Reservation-Station version of FPDIV pipeline.

        * fan-in on inputs (an array of FPADDBaseData: a,b,mid)
        * N-stage divider pipeline
        * fan-out on outputs (an array of FPPackData: z,mid)

        Fan-in and Fan-out are combinatorial.

        :op_wid: - set this to the width of an operator which can
                   then be used to change the behaviour of the pipeline.
    """

    def __init__(self, width, num_rows, op_wid=1):
        self.id_wid = num_bits(width)
        self.pspec = PipelineSpec(width, self.id_wid, op_wid)
        # get the standard mantissa width, store in the pspec HOWEVER...
        fmt = FPFormat.standard(width)
        log2_radix = 2

        # ...4 extra bits on the mantissa: MSB is zero, MSB-1 is 1
        # then there is guard and round at the LSB end.
        # also: round up to nearest radix
        fmt.m_width = roundup(fmt.m_width + 4, log2_radix)

        cfg = DivPipeCoreConfig(fmt.m_width, 0*fmt.fraction_width, log2_radix)

        self.pspec.fpformat = fmt
        self.pspec.log2_radix = log2_radix
        self.pspec.core_config = cfg

        # XXX TODO - a class (or function?) that takes the pspec (right here)
        # and creates... "something".  that "something" MUST have an eq function
        # new_pspec = deepcopy(self.pspec)
        # new_pspec.opkls = DivPipeCoreOperation
        # self.alu = FPDIVBasePipe(new_pspec)
        self.alu = FPDIVBasePipe(self.pspec)
        ReservationStations.__init__(self, num_rows)

    def i_specfn(self):
        return FPADDBaseData(self.pspec)

    def o_specfn(self):
        return FPPackData(self.pspec)
