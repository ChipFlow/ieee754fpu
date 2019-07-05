# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module
from nmigen.cli import main, verilog

from nmutil.singlepipe import ControlBase
from nmutil.concurrentunit import ReservationStations, num_bits

from ieee754.fpcommon.getop import FPADDBaseData
from ieee754.fpcommon.denorm import FPSCData
from ieee754.fpcommon.pack import FPPackData
from ieee754.fpcommon.normtopack import FPNormToPack
from ieee754.fpcommon.postcalc import FPAddStage1Data


from nmigen import Module, Signal, Elaboratable
from math import log

from ieee754.fpcommon.fpbase import FPNumIn, FPNumOut, FPNumBaseRecord
from ieee754.fpcommon.fpbase import FPState, FPNumBase
from ieee754.fpcommon.getop import FPPipeContext

from nmigen import Module, Signal, Cat, Const, Elaboratable

from ieee754.fpcommon.fpbase import FPNumDecode, FPNumBaseRecord
from nmutil.singlepipe import SimpleHandshake, StageChain

from ieee754.fpcommon.fpbase import FPState, FPID
from ieee754.fpcommon.getop import FPADDBaseData


class FPCVTSpecialCasesMod(Elaboratable):
    """ special cases: NaNs, infs, zeros, denormalised
        see "Special Operations"
        https://steve.hollasch.net/cgindex/coding/ieeefloat.html
    """

    def __init__(self, in_pspec, out_pspec):
        self.in_pspec = in_pspec
        self.out_pspec = out_pspec
        self.i = self.ispec()
        self.o = self.ospec()

    def ispec(self):
        return FPADDBaseData(self.in_pspec)

    def ospec(self):
        return FPAddStage1Data(self.out_pspec, e_extra=True)

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        m.submodules.specialcases = self
        m.d.comb += self.i.eq(i)

    def process(self, i):
        return self.o

    def elaborate(self, platform):
        m = Module()

        #m.submodules.sc_out_z = self.o.z

        # decode: XXX really should move to separate stage
        print ("in_width out", self.in_pspec['width'],
                               self.out_pspec['width'])
        a1 = FPNumBaseRecord(self.in_pspec['width'], False)
        print ("a1", a1.width, a1.rmw, a1.e_width, a1.e_start, a1.e_end)
        m.submodules.sc_decode_a = a1 = FPNumDecode(None, a1)
        m.d.comb += a1.v.eq(self.i.a)
        z1 = self.o.z
        print ("z1", z1.width, z1.rmw, z1.e_width, z1.e_start, z1.e_end)

        # set sign
        m.d.comb += self.o.z.s.eq(a1.s)

        # intermediaries
        exp_sub_n126 = Signal((a1.e_width, True), reset_less=True)
        exp_gt127 = Signal(reset_less=True)
        # constants from z1, at the bit-width of a1.
        N126 = Const(z1.fp.N126.value, (a1.e_width, True))
        P127 = Const(z1.fp.P127.value, (a1.e_width, True))
        m.d.comb += exp_sub_n126.eq(a1.e - N126)
        m.d.comb += exp_gt127.eq(a1.e > P127)

        # if a zero, return zero (signed)
        with m.If(a1.exp_n127):
            m.d.comb += self.o.z.zero(a1.s)
            m.d.comb += self.o.out_do_z.eq(1)

        # if a range outside z's min range (-126)
        with m.Elif(exp_sub_n126 < 0):
            m.d.comb += self.o.z.e.eq(a1.e)
            m.d.comb += self.o.z.m.eq(a1.m[-self.o.z.rmw-1:])
            m.d.comb += self.o.of.guard.eq(a1.m[-self.o.z.rmw-2])
            m.d.comb += self.o.of.round_bit.eq(a1.m[-self.o.z.rmw-3])
            m.d.comb += self.o.of.sticky.eq(a1.m[:-self.o.z.rmw-3] != 0)

        # if a is inf return inf 
        with m.Elif(a1.is_inf):
            m.d.comb += self.o.z.inf(a1.s)
            m.d.comb += self.o.out_do_z.eq(1)

        # if a is NaN return NaN
        with m.Elif(a1.is_nan):
            m.d.comb += self.o.z.nan(a1.s)
            m.d.comb += self.o.out_do_z.eq(1)

        # if a mantissa greater than 127, return inf
        with m.Elif(exp_gt127):
            m.d.comb += self.o.z.inf(a1.s)
            m.d.comb += self.o.out_do_z.eq(1)

        # ok after all that, anything else should fit fine (whew)
        with m.Else():
            m.d.comb += self.o.z.e.eq(a1.e)
            print ("alen", a1.e_start, z1.fp.N126, N126)
            print ("m1", self.o.z.rmw, a1.m[-self.o.z.rmw-1:])
            m.d.comb += self.o.z.create(a1.s, a1.e, a1.m[-self.o.z.rmw-1:])
            m.d.comb += self.o.out_do_z.eq(1)

        # copy the context (muxid, operator)
        m.d.comb += self.o.oz.eq(self.o.z.v)
        m.d.comb += self.o.ctx.eq(self.i.ctx)

        return m


class FPCVTSpecialCases(FPState):
    """ special cases: NaNs, infs, zeros, denormalised
    """

    def __init__(self, in_width, out_width, id_wid):
        FPState.__init__(self, "special_cases")
        self.mod = FPCVTSpecialCasesMod(in_width, out_width)
        self.out_z = self.mod.ospec()
        self.out_do_z = Signal(reset_less=True)

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, i, self.out_do_z)
        m.d.sync += self.out_z.v.eq(self.mod.out_z.v) # only take the output
        m.d.sync += self.out_z.ctx.eq(self.mod.o.ctx)  # (and context)

    def action(self, m):
        self.idsync(m)
        with m.If(self.out_do_z):
            m.next = "put_z"
        with m.Else():
            m.next = "denormalise"


class FPCVTSpecialCasesDeNorm(FPState, SimpleHandshake):
    """ special cases: NaNs, infs, zeros, denormalised
    """

    def __init__(self, in_pspec, out_pspec):
        FPState.__init__(self, "special_cases")
        sc = FPCVTSpecialCasesMod(in_pspec, out_pspec)
        SimpleHandshake.__init__(self, sc)
        self.out = self.ospec(None)


class FPCVTBasePipe(ControlBase):
    def __init__(self, in_pspec, out_pspec):
        ControlBase.__init__(self)
        self.pipe1 = FPCVTSpecialCasesDeNorm(in_pspec, out_pspec)
        self.pipe2 = FPNormToPack(out_pspec)

        self._eqs = self.connect([self.pipe1, self.pipe2])

    def elaborate(self, platform):
        m = ControlBase.elaborate(self, platform)
        m.submodules.scnorm = self.pipe1
        m.submodules.normpack = self.pipe2
        m.d.comb += self._eqs
        return m


class FPCVTMuxInOut(ReservationStations):
    """ Reservation-Station version of FPCVT pipeline.

        * fan-in on inputs (an array of FPADDBaseData: a,b,mid)
        * 2-stage multiplier pipeline
        * fan-out on outputs (an array of FPPackData: z,mid)

        Fan-in and Fan-out are combinatorial.
    """
    def __init__(self, in_width, out_width, num_rows, op_wid=0):
        self.op_wid = op_wid
        self.id_wid = num_bits(in_width)
        self.out_id_wid = num_bits(out_width)

        self.in_pspec = {}
        self.in_pspec['id_wid'] = self.id_wid
        self.in_pspec['op_wid'] = self.op_wid
        self.in_pspec['width'] = in_width

        self.out_pspec = {}
        self.out_pspec['id_wid'] = self.out_id_wid
        self.out_pspec['op_wid'] = op_wid
        self.out_pspec['width'] = out_width

        self.alu = FPCVTBasePipe(self.in_pspec, self.out_pspec)
        ReservationStations.__init__(self, num_rows)

    def i_specfn(self):
        return FPADDBaseData(self.in_pspec)

    def o_specfn(self):
        return FPPackData(self.out_pspec)
