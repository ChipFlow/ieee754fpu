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
from fpadd.specialcases import (FPAddSpecialCasesMod, FPAddSpecialCases,
                                FPAddSpecialCasesDeNorm)
from fpcommon.denorm import (FPSCData, FPAddDeNormMod, FPAddDeNorm)
from fpcommon.postcalc import FPAddStage1Data
from fpcommon.postnormalise import (FPNorm1Data, FPNorm1ModSingle,
                            FPNorm1ModMulti, FPNorm1Single, FPNorm1Multi)
from fpcommon.roundz import (FPRoundData, FPRoundMod, FPRound)
from fpcommon.corrections import (FPCorrectionsMod, FPCorrections)
from fpcommon.pack import (FPPackData, FPPackMod, FPPack)
from fpcommon.normtopack import FPNormToPack
from fpcommon.putz import (FPPutZ, FPPutZIdx)


class FPNumIn2Ops:

    def __init__(self, width, id_wid):
        self.a = FPNumIn(None, width)
        self.b = FPNumIn(None, width)
        self.z = FPNumOut(width, False)
        self.out_do_z = Signal(reset_less=True)
        self.oz = Signal(width, reset_less=True)
        self.mid = Signal(id_wid, reset_less=True)

    def eq(self, i):
        return [self.z.eq(i.z), self.out_do_z.eq(i.out_do_z), self.oz.eq(i.oz),
                self.a.eq(i.a), self.b.eq(i.b), self.mid.eq(i.mid)]



class FPAddAlignMultiMod(FPState):

    def __init__(self, width):
        self.in_a = FPNumBase(width)
        self.in_b = FPNumBase(width)
        self.out_a = FPNumIn(None, width)
        self.out_b = FPNumIn(None, width)
        self.exp_eq = Signal(reset_less=True)

    def elaborate(self, platform):
        # This one however (single-cycle) will do the shift
        # in one go.

        m = Module()

        m.submodules.align_in_a = self.in_a
        m.submodules.align_in_b = self.in_b
        m.submodules.align_out_a = self.out_a
        m.submodules.align_out_b = self.out_b

        # NOTE: this does *not* do single-cycle multi-shifting,
        #       it *STAYS* in the align state until exponents match

        # exponent of a greater than b: shift b down
        m.d.comb += self.exp_eq.eq(0)
        m.d.comb += self.out_a.eq(self.in_a)
        m.d.comb += self.out_b.eq(self.in_b)
        agtb = Signal(reset_less=True)
        altb = Signal(reset_less=True)
        m.d.comb += agtb.eq(self.in_a.e > self.in_b.e)
        m.d.comb += altb.eq(self.in_a.e < self.in_b.e)
        with m.If(agtb):
            m.d.comb += self.out_b.shift_down(self.in_b)
        # exponent of b greater than a: shift a down
        with m.Elif(altb):
            m.d.comb += self.out_a.shift_down(self.in_a)
        # exponents equal: move to next stage.
        with m.Else():
            m.d.comb += self.exp_eq.eq(1)
        return m


class FPAddAlignMulti(FPState):

    def __init__(self, width, id_wid):
        FPState.__init__(self, "align")
        self.mod = FPAddAlignMultiMod(width)
        self.out_a = FPNumIn(None, width)
        self.out_b = FPNumIn(None, width)
        self.exp_eq = Signal(reset_less=True)

    def setup(self, m, in_a, in_b):
        """ links module to inputs and outputs
        """
        m.submodules.align = self.mod
        m.d.comb += self.mod.in_a.eq(in_a)
        m.d.comb += self.mod.in_b.eq(in_b)
        m.d.comb += self.exp_eq.eq(self.mod.exp_eq)
        m.d.sync += self.out_a.eq(self.mod.out_a)
        m.d.sync += self.out_b.eq(self.mod.out_b)

    def action(self, m):
        with m.If(self.exp_eq):
            m.next = "add_0"


class FPAddAlignSingleMod:

    def __init__(self, width, id_wid):
        self.width = width
        self.id_wid = id_wid
        self.i = self.ispec()
        self.o = self.ospec()

    def ispec(self):
        return FPSCData(self.width, self.id_wid)

    def ospec(self):
        return FPNumIn2Ops(self.width, self.id_wid)

    def process(self, i):
        return self.o

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        m.submodules.align = self
        m.d.comb += self.i.eq(i)

    def elaborate(self, platform):
        """ Aligns A against B or B against A, depending on which has the
            greater exponent.  This is done in a *single* cycle using
            variable-width bit-shift

            the shifter used here is quite expensive in terms of gates.
            Mux A or B in (and out) into temporaries, as only one of them
            needs to be aligned against the other
        """
        m = Module()

        m.submodules.align_in_a = self.i.a
        m.submodules.align_in_b = self.i.b
        m.submodules.align_out_a = self.o.a
        m.submodules.align_out_b = self.o.b

        # temporary (muxed) input and output to be shifted
        t_inp = FPNumBase(self.width)
        t_out = FPNumIn(None, self.width)
        espec = (len(self.i.a.e), True)
        msr = MultiShiftRMerge(self.i.a.m_width, espec)
        m.submodules.align_t_in = t_inp
        m.submodules.align_t_out = t_out
        m.submodules.multishift_r = msr

        ediff = Signal(espec, reset_less=True)
        ediffr = Signal(espec, reset_less=True)
        tdiff = Signal(espec, reset_less=True)
        elz = Signal(reset_less=True)
        egz = Signal(reset_less=True)

        # connect multi-shifter to t_inp/out mantissa (and tdiff)
        m.d.comb += msr.inp.eq(t_inp.m)
        m.d.comb += msr.diff.eq(tdiff)
        m.d.comb += t_out.m.eq(msr.m)
        m.d.comb += t_out.e.eq(t_inp.e + tdiff)
        m.d.comb += t_out.s.eq(t_inp.s)

        m.d.comb += ediff.eq(self.i.a.e - self.i.b.e)
        m.d.comb += ediffr.eq(self.i.b.e - self.i.a.e)
        m.d.comb += elz.eq(self.i.a.e < self.i.b.e)
        m.d.comb += egz.eq(self.i.a.e > self.i.b.e)

        # default: A-exp == B-exp, A and B untouched (fall through)
        m.d.comb += self.o.a.eq(self.i.a)
        m.d.comb += self.o.b.eq(self.i.b)
        # only one shifter (muxed)
        #m.d.comb += t_out.shift_down_multi(tdiff, t_inp)
        # exponent of a greater than b: shift b down
        with m.If(~self.i.out_do_z):
            with m.If(egz):
                m.d.comb += [t_inp.eq(self.i.b),
                             tdiff.eq(ediff),
                             self.o.b.eq(t_out),
                             self.o.b.s.eq(self.i.b.s), # whoops forgot sign
                            ]
            # exponent of b greater than a: shift a down
            with m.Elif(elz):
                m.d.comb += [t_inp.eq(self.i.a),
                             tdiff.eq(ediffr),
                             self.o.a.eq(t_out),
                             self.o.a.s.eq(self.i.a.s), # whoops forgot sign
                            ]

        m.d.comb += self.o.mid.eq(self.i.mid)
        m.d.comb += self.o.z.eq(self.i.z)
        m.d.comb += self.o.out_do_z.eq(self.i.out_do_z)
        m.d.comb += self.o.oz.eq(self.i.oz)

        return m


class FPAddAlignSingle(FPState):

    def __init__(self, width, id_wid):
        FPState.__init__(self, "align")
        self.mod = FPAddAlignSingleMod(width, id_wid)
        self.out_a = FPNumIn(None, width)
        self.out_b = FPNumIn(None, width)

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, i)

        # NOTE: could be done as comb
        m.d.sync += self.out_a.eq(self.mod.out_a)
        m.d.sync += self.out_b.eq(self.mod.out_b)

    def action(self, m):
        m.next = "add_0"


