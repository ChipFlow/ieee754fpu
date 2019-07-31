# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal, Cat, Mux, Array, Const, Elaboratable
from nmigen.cli import main, verilog
from math import log

from ieee754.fpcommon.fpbase import FPOpIn, FPOpOut
from ieee754.fpcommon.fpbase import Trigger
from nmutil.singlepipe import StageChain

from ieee754.fpcommon.fpbase import FPState, FPID
from ieee754.fpcommon.getop import (FPGetOp, FPBaseData, FPGet2Op)
from ieee754.fpcommon.denorm import (FPSCData, FPAddDeNorm)
from ieee754.fpcommon.postcalc import FPPostCalcData
from ieee754.fpcommon.postnormalise import (FPNorm1Data,
                            FPNorm1Single, FPNorm1Multi)
from ieee754.fpcommon.roundz import (FPRoundData, FPRound)
from ieee754.fpcommon.corrections import FPCorrections
from ieee754.fpcommon.pack import (FPPackData, FPPackMod, FPPack)
from ieee754.fpcommon.normtopack import FPNormToPack
from ieee754.fpcommon.putz import (FPPutZ, FPPutZIdx)

from .specialcases import (FPAddSpecialCases, FPAddSpecialCasesDeNorm)
from .align import (FPAddAlignMulti, FPAddAlignSingle)
from .add0 import (FPAddStage0Data, FPAddStage0)
from .add1 import (FPAddStage1Mod, FPAddStage1)
from .addstages import FPAddAlignSingleAdd


class FPOpData:
    def __init__(self, width, id_wid):
        self.z = FPOpOut(width)
        self.z.data_o = Signal(width)
        self.muxid = Signal(id_wid, reset_less=True)

    def __iter__(self):
        yield self.z
        yield self.muxid

    def eq(self, i):
        return [self.z.eq(i.z), self.muxid.eq(i.mid)]

    def ports(self):
        return list(self)


class FPADDBaseMod(Elaboratable):

    def __init__(self, width, id_wid=None, single_cycle=False, compact=True):
        """ IEEE754 FP Add

            * width: bit-width of IEEE754.  supported: 16, 32, 64
            * id_wid: an identifier that is sync-connected to the input
            * single_cycle: True indicates each stage to complete in 1 clock
            * compact: True indicates a reduced number of stages
        """
        self.width = width
        self.id_wid = id_wid
        self.single_cycle = single_cycle
        self.compact = compact

        self.in_t = Trigger()
        self.i = self.ispec()
        self.o = self.ospec()

        self.states = []

    def ispec(self):
        return FPBaseData(self.width, self.id_wid)

    def ospec(self):
        return FPOpData(self.width, self.id_wid)

    def add_state(self, state):
        self.states.append(state)
        return state

    def elaborate(self, platform=None):
        """ creates the HDL code-fragment for FPAdd
        """
        m = Module()
        m.submodules.out_z = self.o.z
        m.submodules.in_t = self.in_t
        if self.compact:
            self.get_compact_fragment(m, platform)
        else:
            self.get_longer_fragment(m, platform)

        with m.FSM() as fsm:

            for state in self.states:
                with m.State(state.state_from):
                    state.action(m)

        return m

    def get_longer_fragment(self, m, platform=None):

        get = self.add_state(FPGet2Op("get_ops", "special_cases",
                                      self.width))
        get.setup(m, self.i)
        a = get.out_op1
        b = get.out_op2
        get.trigger_setup(m, self.in_t.stb, self.in_t.ack)

        sc = self.add_state(FPAddSpecialCases(self.width, self.id_wid))
        sc.setup(m, a, b, self.in_mid)
        m.submodules.sc = sc

        dn = self.add_state(FPAddDeNorm(self.width, self.id_wid))
        dn.setup(m, a, b, sc.in_mid)
        m.submodules.dn = dn

        if self.single_cycle:
            alm = self.add_state(FPAddAlignSingle(self.width, self.id_wid))
            alm.setup(m, dn.out_a, dn.out_b, dn.in_mid)
        else:
            alm = self.add_state(FPAddAlignMulti(self.width, self.id_wid))
            alm.setup(m, dn.out_a, dn.out_b, dn.in_mid)
        m.submodules.alm = alm

        add0 = self.add_state(FPAddStage0(self.width, self.id_wid))
        add0.setup(m, alm.out_a, alm.out_b, alm.in_mid)
        m.submodules.add0 = add0

        add1 = self.add_state(FPAddStage1(self.width, self.id_wid))
        add1.setup(m, add0.out_tot, add0.out_z, add0.in_mid)
        m.submodules.add1 = add1

        if self.single_cycle:
            n1 = self.add_state(FPNorm1Single(self.width, self.id_wid))
            n1.setup(m, add1.out_z, add1.out_of, add0.in_mid)
        else:
            n1 = self.add_state(FPNorm1Multi(self.width, self.id_wid))
            n1.setup(m, add1.out_z, add1.out_of, add1.norm_stb, add0.in_mid)

        rn = self.add_state(FPRound(self.width, self.id_wid))
        rn.setup(m, n1.out_z, n1.out_roundz, n1.in_mid)

        cor = self.add_state(FPCorrections(self.width, self.id_wid))
        cor.setup(m, rn.out_z, rn.in_mid)

        pa = self.add_state(FPPack(self.width, self.id_wid))
        pa.setup(m, cor.out_z, rn.in_mid)

        ppz = self.add_state(FPPutZ("pack_put_z", pa.out_z, self.out_z,
                                    pa.in_mid, self.out_mid))

        pz = self.add_state(FPPutZ("put_z", sc.out_z, self.out_z,
                                    pa.in_mid, self.out_mid))

    def get_compact_fragment(self, m, platform=None):

        get = FPGet2Op("get_ops", "special_cases", self.width, self.id_wid)
        sc = FPAddSpecialCasesDeNorm(self.width, self.id_wid)
        alm = FPAddAlignSingleAdd(self.width, self.id_wid)
        n1 = FPNormToPack(self.width, self.id_wid)

        get.trigger_setup(m, self.in_t.stb, self.in_t.ack)

        chainlist = [get, sc, alm, n1]
        chain = StageChain(chainlist, specallocate=False)
        chain.setup(m, self.i)
        m.submodules.sc = sc
        m.submodules.alm = alm
        m.submodules.n1 = n1

        for mod in chainlist:
            self.add_state(mod)

        ppz = self.add_state(FPPutZ("pack_put_z", n1.out_z.z, self.o,
                                    n1.out_z.mid, self.o.mid))

        #pz = self.add_state(FPPutZ("put_z", sc.out_z.z, self.o,
        #                            sc.o.mid, self.o.mid))


class FPADDBase(FPState):

    def __init__(self, width, id_wid=None, single_cycle=False):
        """ IEEE754 FP Add

            * width: bit-width of IEEE754.  supported: 16, 32, 64
            * id_wid: an identifier that is sync-connected to the input
            * single_cycle: True indicates each stage to complete in 1 clock
        """
        FPState.__init__(self, "fpadd")
        self.width = width
        self.single_cycle = single_cycle
        self.mod = FPADDBaseMod(width, id_wid, single_cycle)
        self.o = self.ospec()

        self.in_t = Trigger()
        self.i = self.ispec()

        self.z_done = Signal(reset_less=True) # connects to out_z Strobe
        self.in_accept = Signal(reset_less=True)
        self.add_stb = Signal(reset_less=True)
        self.add_ack = Signal(reset=0, reset_less=True)

    def ispec(self):
        return self.mod.ispec()

    def ospec(self):
        return self.mod.ospec()

    def setup(self, m, i, add_stb, in_mid):
        m.d.comb += [self.i.eq(i),
                     self.mod.i.eq(self.i),
                     self.z_done.eq(self.mod.o.z.trigger),
                     #self.add_stb.eq(add_stb),
                     self.mod.in_t.stb.eq(self.in_t.stb),
                     self.in_t.ack.eq(self.mod.in_t.ack),
                     self.o.mid.eq(self.mod.o.mid),
                     self.o.z.v.eq(self.mod.o.z.v),
                     self.o.z.valid_o.eq(self.mod.o.z.valid_o),
                     self.mod.o.z.ready_i.eq(self.o.z.ready_i_test),
                    ]

        m.d.sync += self.add_stb.eq(add_stb)
        m.d.sync += self.add_ack.eq(0) # sets to zero when not in active state
        m.d.sync += self.o.z.ready_i.eq(0) # likewise
        #m.d.sync += self.in_t.stb.eq(0)

        m.submodules.fpadd = self.mod

    def action(self, m):

        # in_accept is set on incoming strobe HIGH and ack LOW.
        m.d.comb += self.in_accept.eq((~self.add_ack) & (self.add_stb))

        #with m.If(self.in_t.ack):
        #    m.d.sync += self.in_t.stb.eq(0)
        with m.If(~self.z_done):
            # not done: test for accepting an incoming operand pair
            with m.If(self.in_accept):
                m.d.sync += [
                    self.add_ack.eq(1), # acknowledge receipt...
                    self.in_t.stb.eq(1), # initiate add
                ]
            with m.Else():
                m.d.sync += [self.add_ack.eq(0),
                             self.in_t.stb.eq(0),
                             self.o.z.ready_i.eq(1),
                            ]
        with m.Else():
            # done: acknowledge, and write out id and value
            m.d.sync += [self.add_ack.eq(1),
                         self.in_t.stb.eq(0)
                        ]
            m.next = "put_z"

            return

            if self.in_mid is not None:
                m.d.sync += self.out_mid.eq(self.mod.out_mid)

            m.d.sync += [
              self.out_z.v.eq(self.mod.out_z.v)
            ]
            # move to output state on detecting z ack
            with m.If(self.out_z.trigger):
                m.d.sync += self.out_z.stb.eq(0)
                m.next = "put_z"
            with m.Else():
                m.d.sync += self.out_z.stb.eq(1)


class FPADD(FPID, Elaboratable):
    """ FPADD: stages as follows:

        FPGetOp (a)
           |
        FPGetOp (b)
           |
        FPAddBase---> FPAddBaseMod
           |            |
        PutZ          GetOps->Specials->Align->Add1/2->Norm->Round/Pack->PutZ

        FPAddBase is tricky: it is both a stage and *has* stages.
        Connection to FPAddBaseMod therefore requires an in stb/ack
        and an out stb/ack.  Just as with Add1-Norm1 interaction, FPGetOp
        needs to be the thing that raises the incoming stb.
    """

    def __init__(self, width, id_wid=None, single_cycle=False, rs_sz=2):
        """ IEEE754 FP Add

            * width: bit-width of IEEE754.  supported: 16, 32, 64
            * id_wid: an identifier that is sync-connected to the input
            * single_cycle: True indicates each stage to complete in 1 clock
        """
        self.width = width
        self.id_wid = id_wid
        self.single_cycle = single_cycle

        #self.out_z = FPOp(width)
        self.ids = FPID(id_wid)

        rs = []
        for i in range(rs_sz):
            in_a  = FPOpIn(width)
            in_b  = FPOpIn(width)
            in_a.data_i = Signal(width)
            in_b.data_i = Signal(width)
            in_a.name = "in_a_%d" % i
            in_b.name = "in_b_%d" % i
            rs.append((in_a, in_b))
        self.rs = Array(rs)

        res = []
        for i in range(rs_sz):
            out_z = FPOpOut(width)
            out_z.data_o = Signal(width)
            out_z.name = "out_z_%d" % i
            res.append(out_z)
        self.res = Array(res)

        self.states = []

    def add_state(self, state):
        self.states.append(state)
        return state

    def elaborate(self, platform=None):
        """ creates the HDL code-fragment for FPAdd
        """
        m = Module()
        #m.submodules += self.rs

        in_a = self.rs[0][0]
        in_b = self.rs[0][1]

        geta = self.add_state(FPGetOp("get_a", "get_b",
                                      in_a, self.width))
        geta.setup(m, in_a)
        a = geta.out_op

        getb = self.add_state(FPGetOp("get_b", "fpadd",
                                      in_b, self.width))
        getb.setup(m, in_b)
        b = getb.out_op

        ab = FPADDBase(self.width, self.id_wid, self.single_cycle)
        ab = self.add_state(ab)
        abd = ab.ispec() # create an input spec object for FPADDBase
        m.d.sync += [abd.a.eq(a), abd.b.eq(b), abd.mid.eq(self.ids.in_mid)]
        ab.setup(m, abd, getb.out_decode, self.ids.in_mid)
        o = ab.o

        pz = self.add_state(FPPutZIdx("put_z", o.z, self.res,
                                    o.mid, "get_a"))

        with m.FSM() as fsm:

            for state in self.states:
                with m.State(state.state_from):
                    state.action(m)

        return m


if __name__ == "__main__":
    if True:
        alu = FPADD(width=32, id_wid=5, single_cycle=True)
        main(alu, ports=alu.rs[0][0].ports() + \
                        alu.rs[0][1].ports() + \
                        alu.res[0].ports() + \
                        [alu.ids.in_mid, alu.ids.out_mid])
    else:
        alu = FPADDBase(width=32, id_wid=5, single_cycle=True)
        main(alu, ports=[alu.in_a, alu.in_b] + \
                        alu.in_t.ports() + \
                        alu.out_z.ports() + \
                        [alu.in_mid, alu.out_mid])


    # works... but don't use, just do "python fname.py convert -t v"
    #print (verilog.convert(alu, ports=[
    #                        ports=alu.in_a.ports() + \
    #                              alu.in_b.ports() + \
    #                              alu.out_z.ports())
