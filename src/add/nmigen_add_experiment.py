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

from fpbase import FPState
from fpcommon.getop import (FPGetOpMod, FPGetOp, FPNumBase2Ops, FPADDBaseData,                              FPGet2OpMod, FPGet2Op)
from fpcommon.denorm import (FPSCData, FPAddDeNormMod, FPAddDeNorm)


class FPAddSpecialCasesMod:
    """ special cases: NaNs, infs, zeros, denormalised
        NOTE: some of these are unique to add.  see "Special Operations"
        https://steve.hollasch.net/cgindex/coding/ieeefloat.html
    """

    def __init__(self, width, id_wid):
        self.width = width
        self.id_wid = id_wid
        self.i = self.ispec()
        self.o = self.ospec()

    def ispec(self):
        return FPADDBaseData(self.width, self.id_wid)

    def ospec(self):
        return FPSCData(self.width, self.id_wid)

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        m.submodules.specialcases = self
        m.d.comb += self.i.eq(i)

    def process(self, i):
        return self.o

    def elaborate(self, platform):
        m = Module()

        m.submodules.sc_out_z = self.o.z

        # decode: XXX really should move to separate stage
        a1 = FPNumIn(None, self.width)
        b1 = FPNumIn(None, self.width)
        m.submodules.sc_decode_a = a1
        m.submodules.sc_decode_b = b1
        m.d.comb += [a1.decode(self.i.a),
                     b1.decode(self.i.b),
                    ]

        s_nomatch = Signal()
        m.d.comb += s_nomatch.eq(a1.s != b1.s)

        m_match = Signal()
        m.d.comb += m_match.eq(a1.m == b1.m)

        # if a is NaN or b is NaN return NaN
        with m.If(a1.is_nan | b1.is_nan):
            m.d.comb += self.o.out_do_z.eq(1)
            m.d.comb += self.o.z.nan(0)

        # XXX WEIRDNESS for FP16 non-canonical NaN handling
        # under review

        ## if a is zero and b is NaN return -b
        #with m.If(a.is_zero & (a.s==0) & b.is_nan):
        #    m.d.comb += self.o.out_do_z.eq(1)
        #    m.d.comb += z.create(b.s, b.e, Cat(b.m[3:-2], ~b.m[0]))

        ## if b is zero and a is NaN return -a
        #with m.Elif(b.is_zero & (b.s==0) & a.is_nan):
        #    m.d.comb += self.o.out_do_z.eq(1)
        #    m.d.comb += z.create(a.s, a.e, Cat(a.m[3:-2], ~a.m[0]))

        ## if a is -zero and b is NaN return -b
        #with m.Elif(a.is_zero & (a.s==1) & b.is_nan):
        #    m.d.comb += self.o.out_do_z.eq(1)
        #    m.d.comb += z.create(a.s & b.s, b.e, Cat(b.m[3:-2], 1))

        ## if b is -zero and a is NaN return -a
        #with m.Elif(b.is_zero & (b.s==1) & a.is_nan):
        #    m.d.comb += self.o.out_do_z.eq(1)
        #    m.d.comb += z.create(a.s & b.s, a.e, Cat(a.m[3:-2], 1))

        # if a is inf return inf (or NaN)
        with m.Elif(a1.is_inf):
            m.d.comb += self.o.out_do_z.eq(1)
            m.d.comb += self.o.z.inf(a1.s)
            # if a is inf and signs don't match return NaN
            with m.If(b1.exp_128 & s_nomatch):
                m.d.comb += self.o.z.nan(0)

        # if b is inf return inf
        with m.Elif(b1.is_inf):
            m.d.comb += self.o.out_do_z.eq(1)
            m.d.comb += self.o.z.inf(b1.s)

        # if a is zero and b zero return signed-a/b
        with m.Elif(a1.is_zero & b1.is_zero):
            m.d.comb += self.o.out_do_z.eq(1)
            m.d.comb += self.o.z.create(a1.s & b1.s, b1.e, b1.m[3:-1])

        # if a is zero return b
        with m.Elif(a1.is_zero):
            m.d.comb += self.o.out_do_z.eq(1)
            m.d.comb += self.o.z.create(b1.s, b1.e, b1.m[3:-1])

        # if b is zero return a
        with m.Elif(b1.is_zero):
            m.d.comb += self.o.out_do_z.eq(1)
            m.d.comb += self.o.z.create(a1.s, a1.e, a1.m[3:-1])

        # if a equal to -b return zero (+ve zero)
        with m.Elif(s_nomatch & m_match & (a1.e == b1.e)):
            m.d.comb += self.o.out_do_z.eq(1)
            m.d.comb += self.o.z.zero(0)

        # Denormalised Number checks next, so pass a/b data through
        with m.Else():
            m.d.comb += self.o.out_do_z.eq(0)
            m.d.comb += self.o.a.eq(a1)
            m.d.comb += self.o.b.eq(b1)

        m.d.comb += self.o.oz.eq(self.o.z.v)
        m.d.comb += self.o.mid.eq(self.i.mid)

        return m


class FPID:
    def __init__(self, id_wid):
        self.id_wid = id_wid
        if self.id_wid:
            self.in_mid = Signal(id_wid, reset_less=True)
            self.out_mid = Signal(id_wid, reset_less=True)
        else:
            self.in_mid = None
            self.out_mid = None

    def idsync(self, m):
        if self.id_wid is not None:
            m.d.sync += self.out_mid.eq(self.in_mid)


class FPAddSpecialCases(FPState):
    """ special cases: NaNs, infs, zeros, denormalised
        NOTE: some of these are unique to add.  see "Special Operations"
        https://steve.hollasch.net/cgindex/coding/ieeefloat.html
    """

    def __init__(self, width, id_wid):
        FPState.__init__(self, "special_cases")
        self.mod = FPAddSpecialCasesMod(width)
        self.out_z = self.mod.ospec()
        self.out_do_z = Signal(reset_less=True)

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, i, self.out_do_z)
        m.d.sync += self.out_z.v.eq(self.mod.out_z.v) # only take the output
        m.d.sync += self.out_z.mid.eq(self.mod.o.mid)  # (and mid)

    def action(self, m):
        self.idsync(m)
        with m.If(self.out_do_z):
            m.next = "put_z"
        with m.Else():
            m.next = "denormalise"


class FPAddSpecialCasesDeNorm(FPState, UnbufferedPipeline):
    """ special cases: NaNs, infs, zeros, denormalised
        NOTE: some of these are unique to add.  see "Special Operations"
        https://steve.hollasch.net/cgindex/coding/ieeefloat.html
    """

    def __init__(self, width, id_wid):
        FPState.__init__(self, "special_cases")
        self.width = width
        self.id_wid = id_wid
        UnbufferedPipeline.__init__(self, self) # pipe is its own stage
        self.out = self.ospec()

    def ispec(self):
        return FPADDBaseData(self.width, self.id_wid) # SpecialCases ispec

    def ospec(self):
        return FPSCData(self.width, self.id_wid) # DeNorm ospec

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        smod = FPAddSpecialCasesMod(self.width, self.id_wid)
        dmod = FPAddDeNormMod(self.width, self.id_wid)

        chain = StageChain([smod, dmod])
        chain.setup(m, i)

        # only needed for break-out (early-out)
        # self.out_do_z = smod.o.out_do_z

        self.o = dmod.o

    def process(self, i):
        return self.o

    def action(self, m):
        # for break-out (early-out)
        #with m.If(self.out_do_z):
        #    m.next = "put_z"
        #with m.Else():
            m.d.sync += self.out.eq(self.process(None))
            m.next = "align"


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


class FPAddAlignSingleAdd(FPState, UnbufferedPipeline):

    def __init__(self, width, id_wid):
        FPState.__init__(self, "align")
        self.width = width
        self.id_wid = id_wid
        UnbufferedPipeline.__init__(self, self) # pipeline is its own stage
        self.a1o = self.ospec()

    def ispec(self):
        return FPSCData(self.width, self.id_wid)

    def ospec(self):
        return FPAddStage1Data(self.width, self.id_wid) # AddStage1 ospec

    def setup(self, m, i):
        """ links module to inputs and outputs
        """

        # chain AddAlignSingle, AddStage0 and AddStage1
        mod = FPAddAlignSingleMod(self.width, self.id_wid)
        a0mod = FPAddStage0Mod(self.width, self.id_wid)
        a1mod = FPAddStage1Mod(self.width, self.id_wid)

        chain = StageChain([mod, a0mod, a1mod])
        chain.setup(m, i)

        self.o = a1mod.o

    def process(self, i):
        return self.o

    def action(self, m):
        m.d.sync += self.a1o.eq(self.process(None))
        m.next = "normalise_1"


class FPAddStage0Data:

    def __init__(self, width, id_wid):
        self.z = FPNumBase(width, False)
        self.out_do_z = Signal(reset_less=True)
        self.oz = Signal(width, reset_less=True)
        self.tot = Signal(self.z.m_width + 4, reset_less=True)
        self.mid = Signal(id_wid, reset_less=True)

    def eq(self, i):
        return [self.z.eq(i.z), self.out_do_z.eq(i.out_do_z), self.oz.eq(i.oz),
                self.tot.eq(i.tot), self.mid.eq(i.mid)]


class FPAddStage0Mod:

    def __init__(self, width, id_wid):
        self.width = width
        self.id_wid = id_wid
        self.i = self.ispec()
        self.o = self.ospec()

    def ispec(self):
        return FPSCData(self.width, self.id_wid)

    def ospec(self):
        return FPAddStage0Data(self.width, self.id_wid)

    def process(self, i):
        return self.o

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        m.submodules.add0 = self
        m.d.comb += self.i.eq(i)

    def elaborate(self, platform):
        m = Module()
        m.submodules.add0_in_a = self.i.a
        m.submodules.add0_in_b = self.i.b
        m.submodules.add0_out_z = self.o.z

        # store intermediate tests (and zero-extended mantissas)
        seq = Signal(reset_less=True)
        mge = Signal(reset_less=True)
        am0 = Signal(len(self.i.a.m)+1, reset_less=True)
        bm0 = Signal(len(self.i.b.m)+1, reset_less=True)
        m.d.comb += [seq.eq(self.i.a.s == self.i.b.s),
                     mge.eq(self.i.a.m >= self.i.b.m),
                     am0.eq(Cat(self.i.a.m, 0)),
                     bm0.eq(Cat(self.i.b.m, 0))
                    ]
        # same-sign (both negative or both positive) add mantissas
        with m.If(~self.i.out_do_z):
            m.d.comb += self.o.z.e.eq(self.i.a.e)
            with m.If(seq):
                m.d.comb += [
                    self.o.tot.eq(am0 + bm0),
                    self.o.z.s.eq(self.i.a.s)
                ]
            # a mantissa greater than b, use a
            with m.Elif(mge):
                m.d.comb += [
                    self.o.tot.eq(am0 - bm0),
                    self.o.z.s.eq(self.i.a.s)
                ]
            # b mantissa greater than a, use b
            with m.Else():
                m.d.comb += [
                    self.o.tot.eq(bm0 - am0),
                    self.o.z.s.eq(self.i.b.s)
            ]

        m.d.comb += self.o.oz.eq(self.i.oz)
        m.d.comb += self.o.out_do_z.eq(self.i.out_do_z)
        m.d.comb += self.o.mid.eq(self.i.mid)
        return m


class FPAddStage0(FPState):
    """ First stage of add.  covers same-sign (add) and subtract
        special-casing when mantissas are greater or equal, to
        give greatest accuracy.
    """

    def __init__(self, width, id_wid):
        FPState.__init__(self, "add_0")
        self.mod = FPAddStage0Mod(width)
        self.o = self.mod.ospec()

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, i)

        # NOTE: these could be done as combinatorial (merge add0+add1)
        m.d.sync += self.o.eq(self.mod.o)

    def action(self, m):
        m.next = "add_1"


class FPAddStage1Data:

    def __init__(self, width, id_wid):
        self.z = FPNumBase(width, False)
        self.out_do_z = Signal(reset_less=True)
        self.oz = Signal(width, reset_less=True)
        self.of = Overflow()
        self.mid = Signal(id_wid, reset_less=True)

    def eq(self, i):
        return [self.z.eq(i.z), self.out_do_z.eq(i.out_do_z), self.oz.eq(i.oz),
                self.of.eq(i.of), self.mid.eq(i.mid)]



class FPAddStage1Mod(FPState):
    """ Second stage of add: preparation for normalisation.
        detects when tot sum is too big (tot[27] is kinda a carry bit)
    """

    def __init__(self, width, id_wid):
        self.width = width
        self.id_wid = id_wid
        self.i = self.ispec()
        self.o = self.ospec()

    def ispec(self):
        return FPAddStage0Data(self.width, self.id_wid)

    def ospec(self):
        return FPAddStage1Data(self.width, self.id_wid)

    def process(self, i):
        return self.o

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        m.submodules.add1 = self
        m.submodules.add1_out_overflow = self.o.of

        m.d.comb += self.i.eq(i)

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.o.z.eq(self.i.z)
        # tot[-1] (MSB) gets set when the sum overflows. shift result down
        with m.If(~self.i.out_do_z):
            with m.If(self.i.tot[-1]):
                m.d.comb += [
                    self.o.z.m.eq(self.i.tot[4:]),
                    self.o.of.m0.eq(self.i.tot[4]),
                    self.o.of.guard.eq(self.i.tot[3]),
                    self.o.of.round_bit.eq(self.i.tot[2]),
                    self.o.of.sticky.eq(self.i.tot[1] | self.i.tot[0]),
                    self.o.z.e.eq(self.i.z.e + 1)
            ]
            # tot[-1] (MSB) zero case
            with m.Else():
                m.d.comb += [
                    self.o.z.m.eq(self.i.tot[3:]),
                    self.o.of.m0.eq(self.i.tot[3]),
                    self.o.of.guard.eq(self.i.tot[2]),
                    self.o.of.round_bit.eq(self.i.tot[1]),
                    self.o.of.sticky.eq(self.i.tot[0])
            ]

        m.d.comb += self.o.out_do_z.eq(self.i.out_do_z)
        m.d.comb += self.o.oz.eq(self.i.oz)
        m.d.comb += self.o.mid.eq(self.i.mid)

        return m


class FPAddStage1(FPState):

    def __init__(self, width, id_wid):
        FPState.__init__(self, "add_1")
        self.mod = FPAddStage1Mod(width)
        self.out_z = FPNumBase(width, False)
        self.out_of = Overflow()
        self.norm_stb = Signal()

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, i)

        m.d.sync += self.norm_stb.eq(0) # sets to zero when not in add1 state

        m.d.sync += self.out_of.eq(self.mod.out_of)
        m.d.sync += self.out_z.eq(self.mod.out_z)
        m.d.sync += self.norm_stb.eq(1)

    def action(self, m):
        m.next = "normalise_1"


class FPNormaliseModSingle:

    def __init__(self, width):
        self.width = width
        self.in_z = self.ispec()
        self.out_z = self.ospec()

    def ispec(self):
        return FPNumBase(self.width, False)

    def ospec(self):
        return FPNumBase(self.width, False)

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        m.submodules.normalise = self
        m.d.comb += self.i.eq(i)

    def elaborate(self, platform):
        m = Module()

        mwid = self.out_z.m_width+2
        pe = PriorityEncoder(mwid)
        m.submodules.norm_pe = pe

        m.submodules.norm1_out_z = self.out_z
        m.submodules.norm1_in_z = self.in_z

        in_z = FPNumBase(self.width, False)
        in_of = Overflow()
        m.submodules.norm1_insel_z = in_z
        m.submodules.norm1_insel_overflow = in_of

        espec = (len(in_z.e), True)
        ediff_n126 = Signal(espec, reset_less=True)
        msr = MultiShiftRMerge(mwid, espec)
        m.submodules.multishift_r = msr

        m.d.comb += in_z.eq(self.in_z)
        m.d.comb += in_of.eq(self.in_of)
        # initialise out from in (overridden below)
        m.d.comb += self.out_z.eq(in_z)
        m.d.comb += self.out_of.eq(in_of)
        # normalisation decrease condition
        decrease = Signal(reset_less=True)
        m.d.comb += decrease.eq(in_z.m_msbzero)
        # decrease exponent
        with m.If(decrease):
            # *sigh* not entirely obvious: count leading zeros (clz)
            # with a PriorityEncoder: to find from the MSB
            # we reverse the order of the bits.
            temp_m = Signal(mwid, reset_less=True)
            temp_s = Signal(mwid+1, reset_less=True)
            clz = Signal((len(in_z.e), True), reset_less=True)
            m.d.comb += [
                # cat round and guard bits back into the mantissa
                temp_m.eq(Cat(in_of.round_bit, in_of.guard, in_z.m)),
                pe.i.eq(temp_m[::-1]),          # inverted
                clz.eq(pe.o),                   # count zeros from MSB down
                temp_s.eq(temp_m << clz),       # shift mantissa UP
                self.out_z.e.eq(in_z.e - clz),  # DECREASE exponent
                self.out_z.m.eq(temp_s[2:]),    # exclude bits 0&1
            ]

        return m


class FPNorm1Data:

    def __init__(self, width, id_wid):
        self.roundz = Signal(reset_less=True)
        self.z = FPNumBase(width, False)
        self.out_do_z = Signal(reset_less=True)
        self.oz = Signal(width, reset_less=True)
        self.mid = Signal(id_wid, reset_less=True)

    def eq(self, i):
        return [self.z.eq(i.z), self.out_do_z.eq(i.out_do_z), self.oz.eq(i.oz),
                self.roundz.eq(i.roundz), self.mid.eq(i.mid)]


class FPNorm1ModSingle:

    def __init__(self, width, id_wid):
        self.width = width
        self.id_wid = id_wid
        self.i = self.ispec()
        self.o = self.ospec()

    def ispec(self):
        return FPAddStage1Data(self.width, self.id_wid)

    def ospec(self):
        return FPNorm1Data(self.width, self.id_wid)

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        m.submodules.normalise_1 = self
        m.d.comb += self.i.eq(i)

    def process(self, i):
        return self.o

    def elaborate(self, platform):
        m = Module()

        mwid = self.o.z.m_width+2
        pe = PriorityEncoder(mwid)
        m.submodules.norm_pe = pe

        of = Overflow()
        m.d.comb += self.o.roundz.eq(of.roundz)

        m.submodules.norm1_out_z = self.o.z
        m.submodules.norm1_out_overflow = of
        m.submodules.norm1_in_z = self.i.z
        m.submodules.norm1_in_overflow = self.i.of

        i = self.ispec()
        m.submodules.norm1_insel_z = i.z
        m.submodules.norm1_insel_overflow = i.of

        espec = (len(i.z.e), True)
        ediff_n126 = Signal(espec, reset_less=True)
        msr = MultiShiftRMerge(mwid, espec)
        m.submodules.multishift_r = msr

        m.d.comb += i.eq(self.i)
        # initialise out from in (overridden below)
        m.d.comb += self.o.z.eq(i.z)
        m.d.comb += of.eq(i.of)
        # normalisation increase/decrease conditions
        decrease = Signal(reset_less=True)
        increase = Signal(reset_less=True)
        m.d.comb += decrease.eq(i.z.m_msbzero & i.z.exp_gt_n126)
        m.d.comb += increase.eq(i.z.exp_lt_n126)
        # decrease exponent
        with m.If(~self.i.out_do_z):
            with m.If(decrease):
                # *sigh* not entirely obvious: count leading zeros (clz)
                # with a PriorityEncoder: to find from the MSB
                # we reverse the order of the bits.
                temp_m = Signal(mwid, reset_less=True)
                temp_s = Signal(mwid+1, reset_less=True)
                clz = Signal((len(i.z.e), True), reset_less=True)
                # make sure that the amount to decrease by does NOT
                # go below the minimum non-INF/NaN exponent
                limclz = Mux(i.z.exp_sub_n126 > pe.o, pe.o,
                             i.z.exp_sub_n126)
                m.d.comb += [
                    # cat round and guard bits back into the mantissa
                    temp_m.eq(Cat(i.of.round_bit, i.of.guard, i.z.m)),
                    pe.i.eq(temp_m[::-1]),          # inverted
                    clz.eq(limclz),                 # count zeros from MSB down
                    temp_s.eq(temp_m << clz),       # shift mantissa UP
                    self.o.z.e.eq(i.z.e - clz),  # DECREASE exponent
                    self.o.z.m.eq(temp_s[2:]),    # exclude bits 0&1
                    of.m0.eq(temp_s[2]),          # copy of mantissa[0]
                    # overflow in bits 0..1: got shifted too (leave sticky)
                    of.guard.eq(temp_s[1]),       # guard
                    of.round_bit.eq(temp_s[0]),   # round
                ]
            # increase exponent
            with m.Elif(increase):
                temp_m = Signal(mwid+1, reset_less=True)
                m.d.comb += [
                    temp_m.eq(Cat(i.of.sticky, i.of.round_bit, i.of.guard,
                                  i.z.m)),
                    ediff_n126.eq(i.z.N126 - i.z.e),
                    # connect multi-shifter to inp/out mantissa (and ediff)
                    msr.inp.eq(temp_m),
                    msr.diff.eq(ediff_n126),
                    self.o.z.m.eq(msr.m[3:]),
                    of.m0.eq(temp_s[3]),   # copy of mantissa[0]
                    # overflow in bits 0..1: got shifted too (leave sticky)
                    of.guard.eq(temp_s[2]),     # guard
                    of.round_bit.eq(temp_s[1]), # round
                    of.sticky.eq(temp_s[0]),    # sticky
                    self.o.z.e.eq(i.z.e + ediff_n126),
                ]

        m.d.comb += self.o.mid.eq(self.i.mid)
        m.d.comb += self.o.out_do_z.eq(self.i.out_do_z)
        m.d.comb += self.o.oz.eq(self.i.oz)

        return m


class FPNorm1ModMulti:

    def __init__(self, width, single_cycle=True):
        self.width = width
        self.in_select = Signal(reset_less=True)
        self.in_z = FPNumBase(width, False)
        self.in_of = Overflow()
        self.temp_z = FPNumBase(width, False)
        self.temp_of = Overflow()
        self.out_z = FPNumBase(width, False)
        self.out_of = Overflow()

    def elaborate(self, platform):
        m = Module()

        m.submodules.norm1_out_z = self.out_z
        m.submodules.norm1_out_overflow = self.out_of
        m.submodules.norm1_temp_z = self.temp_z
        m.submodules.norm1_temp_of = self.temp_of
        m.submodules.norm1_in_z = self.in_z
        m.submodules.norm1_in_overflow = self.in_of

        in_z = FPNumBase(self.width, False)
        in_of = Overflow()
        m.submodules.norm1_insel_z = in_z
        m.submodules.norm1_insel_overflow = in_of

        # select which of temp or in z/of to use
        with m.If(self.in_select):
            m.d.comb += in_z.eq(self.in_z)
            m.d.comb += in_of.eq(self.in_of)
        with m.Else():
            m.d.comb += in_z.eq(self.temp_z)
            m.d.comb += in_of.eq(self.temp_of)
        # initialise out from in (overridden below)
        m.d.comb += self.out_z.eq(in_z)
        m.d.comb += self.out_of.eq(in_of)
        # normalisation increase/decrease conditions
        decrease = Signal(reset_less=True)
        increase = Signal(reset_less=True)
        m.d.comb += decrease.eq(in_z.m_msbzero & in_z.exp_gt_n126)
        m.d.comb += increase.eq(in_z.exp_lt_n126)
        m.d.comb += self.out_norm.eq(decrease | increase) # loop-end
        # decrease exponent
        with m.If(decrease):
            m.d.comb += [
                self.out_z.e.eq(in_z.e - 1),  # DECREASE exponent
                self.out_z.m.eq(in_z.m << 1), # shift mantissa UP
                self.out_z.m[0].eq(in_of.guard), # steal guard (was tot[2])
                self.out_of.guard.eq(in_of.round_bit), # round (was tot[1])
                self.out_of.round_bit.eq(0),        # reset round bit
                self.out_of.m0.eq(in_of.guard),
            ]
        # increase exponent
        with m.Elif(increase):
            m.d.comb += [
                self.out_z.e.eq(in_z.e + 1),  # INCREASE exponent
                self.out_z.m.eq(in_z.m >> 1), # shift mantissa DOWN
                self.out_of.guard.eq(in_z.m[0]),
                self.out_of.m0.eq(in_z.m[1]),
                self.out_of.round_bit.eq(in_of.guard),
                self.out_of.sticky.eq(in_of.sticky | in_of.round_bit)
            ]

        return m


class FPNorm1Single(FPState):

    def __init__(self, width, id_wid, single_cycle=True):
        FPState.__init__(self, "normalise_1")
        self.mod = FPNorm1ModSingle(width)
        self.o = self.ospec()
        self.out_z = FPNumBase(width, False)
        self.out_roundz = Signal(reset_less=True)

    def ispec(self):
        return self.mod.ispec()

    def ospec(self):
        return self.mod.ospec()

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, i)

    def action(self, m):
        m.next = "round"


class FPNorm1Multi(FPState):

    def __init__(self, width, id_wid):
        FPState.__init__(self, "normalise_1")
        self.mod = FPNorm1ModMulti(width)
        self.stb = Signal(reset_less=True)
        self.ack = Signal(reset=0, reset_less=True)
        self.out_norm = Signal(reset_less=True)
        self.in_accept = Signal(reset_less=True)
        self.temp_z = FPNumBase(width)
        self.temp_of = Overflow()
        self.out_z = FPNumBase(width)
        self.out_roundz = Signal(reset_less=True)

    def setup(self, m, in_z, in_of, norm_stb):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, in_z, in_of, norm_stb,
                       self.in_accept, self.temp_z, self.temp_of,
                       self.out_z, self.out_norm)

        m.d.comb += self.stb.eq(norm_stb)
        m.d.sync += self.ack.eq(0) # sets to zero when not in normalise_1 state

    def action(self, m):
        m.d.comb += self.in_accept.eq((~self.ack) & (self.stb))
        m.d.sync += self.temp_of.eq(self.mod.out_of)
        m.d.sync += self.temp_z.eq(self.out_z)
        with m.If(self.out_norm):
            with m.If(self.in_accept):
                m.d.sync += [
                    self.ack.eq(1),
                ]
            with m.Else():
                m.d.sync += self.ack.eq(0)
        with m.Else():
            # normalisation not required (or done).
            m.next = "round"
            m.d.sync += self.ack.eq(1)
            m.d.sync += self.out_roundz.eq(self.mod.out_of.roundz)


class FPNormToPack(FPState, UnbufferedPipeline):

    def __init__(self, width, id_wid):
        FPState.__init__(self, "normalise_1")
        self.id_wid = id_wid
        self.width = width
        UnbufferedPipeline.__init__(self, self) # pipeline is its own stage

    def ispec(self):
        return FPAddStage1Data(self.width, self.id_wid) # Norm1ModSingle ispec

    def ospec(self):
        return FPPackData(self.width, self.id_wid) # FPPackMod ospec

    def setup(self, m, i):
        """ links module to inputs and outputs
        """

        # Normalisation, Rounding Corrections, Pack - in a chain
        nmod = FPNorm1ModSingle(self.width, self.id_wid)
        rmod = FPRoundMod(self.width, self.id_wid)
        cmod = FPCorrectionsMod(self.width, self.id_wid)
        pmod = FPPackMod(self.width, self.id_wid)
        chain = StageChain([nmod, rmod, cmod, pmod])
        chain.setup(m, i)
        self.out_z = pmod.ospec()

        self.o = pmod.o

    def process(self, i):
        return self.o

    def action(self, m):
        m.d.sync += self.out_z.eq(self.process(None))
        m.next = "pack_put_z"


class FPRoundData:

    def __init__(self, width, id_wid):
        self.z = FPNumBase(width, False)
        self.out_do_z = Signal(reset_less=True)
        self.oz = Signal(width, reset_less=True)
        self.mid = Signal(id_wid, reset_less=True)

    def eq(self, i):
        return [self.z.eq(i.z), self.out_do_z.eq(i.out_do_z), self.oz.eq(i.oz),
                self.mid.eq(i.mid)]


class FPRoundMod:

    def __init__(self, width, id_wid):
        self.width = width
        self.id_wid = id_wid
        self.i = self.ispec()
        self.out_z = self.ospec()

    def ispec(self):
        return FPNorm1Data(self.width, self.id_wid)

    def ospec(self):
        return FPRoundData(self.width, self.id_wid)

    def process(self, i):
        return self.out_z

    def setup(self, m, i):
        m.submodules.roundz = self
        m.d.comb += self.i.eq(i)

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.out_z.eq(self.i) # copies mid, z, out_do_z
        with m.If(~self.i.out_do_z):
            with m.If(self.i.roundz):
                m.d.comb += self.out_z.z.m.eq(self.i.z.m + 1) # mantissa up
                with m.If(self.i.z.m == self.i.z.m1s): # all 1s
                    m.d.comb += self.out_z.z.e.eq(self.i.z.e + 1) # exponent up

        return m


class FPRound(FPState):

    def __init__(self, width, id_wid):
        FPState.__init__(self, "round")
        self.mod = FPRoundMod(width)
        self.out_z = self.ospec()

    def ispec(self):
        return self.mod.ispec()

    def ospec(self):
        return self.mod.ospec()

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, i)

        self.idsync(m)
        m.d.sync += self.out_z.eq(self.mod.out_z)
        m.d.sync += self.out_z.mid.eq(self.mod.o.mid)

    def action(self, m):
        m.next = "corrections"


class FPCorrectionsMod:

    def __init__(self, width, id_wid):
        self.width = width
        self.id_wid = id_wid
        self.i = self.ispec()
        self.out_z = self.ospec()

    def ispec(self):
        return FPRoundData(self.width, self.id_wid)

    def ospec(self):
        return FPRoundData(self.width, self.id_wid)

    def process(self, i):
        return self.out_z

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        m.submodules.corrections = self
        m.d.comb += self.i.eq(i)

    def elaborate(self, platform):
        m = Module()
        m.submodules.corr_in_z = self.i.z
        m.submodules.corr_out_z = self.out_z.z
        m.d.comb += self.out_z.eq(self.i) # copies mid, z, out_do_z
        with m.If(~self.i.out_do_z):
            with m.If(self.i.z.is_denormalised):
                m.d.comb += self.out_z.z.e.eq(self.i.z.N127)
        return m


class FPCorrections(FPState):

    def __init__(self, width, id_wid):
        FPState.__init__(self, "corrections")
        self.mod = FPCorrectionsMod(width)
        self.out_z = self.ospec()

    def ispec(self):
        return self.mod.ispec()

    def ospec(self):
        return self.mod.ospec()

    def setup(self, m, in_z):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, in_z)

        m.d.sync += self.out_z.eq(self.mod.out_z)
        m.d.sync += self.out_z.mid.eq(self.mod.o.mid)

    def action(self, m):
        m.next = "pack"


class FPPackData:

    def __init__(self, width, id_wid):
        self.z = Signal(width, reset_less=True)
        self.mid = Signal(id_wid, reset_less=True)

    def eq(self, i):
        return [self.z.eq(i.z), self.mid.eq(i.mid)]

    def ports(self):
        return [self.z, self.mid]


class FPPackMod:

    def __init__(self, width, id_wid):
        self.width = width
        self.id_wid = id_wid
        self.i = self.ispec()
        self.o = self.ospec()

    def ispec(self):
        return FPRoundData(self.width, self.id_wid)

    def ospec(self):
        return FPPackData(self.width, self.id_wid)

    def process(self, i):
        return self.o

    def setup(self, m, in_z):
        """ links module to inputs and outputs
        """
        m.submodules.pack = self
        m.d.comb += self.i.eq(in_z)

    def elaborate(self, platform):
        m = Module()
        z = FPNumOut(self.width, False)
        m.submodules.pack_in_z = self.i.z
        m.submodules.pack_out_z = z
        m.d.comb += self.o.mid.eq(self.i.mid)
        with m.If(~self.i.out_do_z):
            with m.If(self.i.z.is_overflowed):
                m.d.comb += z.inf(self.i.z.s)
            with m.Else():
                m.d.comb += z.create(self.i.z.s, self.i.z.e, self.i.z.m)
        with m.Else():
            m.d.comb += z.v.eq(self.i.oz)
        m.d.comb += self.o.z.eq(z.v)
        return m


class FPPack(FPState):

    def __init__(self, width, id_wid):
        FPState.__init__(self, "pack")
        self.mod = FPPackMod(width)
        self.out_z = self.ospec()

    def ispec(self):
        return self.mod.ispec()

    def ospec(self):
        return self.mod.ospec()

    def setup(self, m, in_z):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, in_z)

        m.d.sync += self.out_z.v.eq(self.mod.out_z.v)
        m.d.sync += self.out_z.mid.eq(self.mod.o.mid)

    def action(self, m):
        m.next = "pack_put_z"


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


class FPOpData:
    def __init__(self, width, id_wid):
        self.z = FPOp(width)
        self.mid = Signal(id_wid, reset_less=True)

    def eq(self, i):
        return [self.z.eq(i.z), self.mid.eq(i.mid)]

    def ports(self):
        return [self.z, self.mid]


class FPADDBaseMod:

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
        return FPADDBaseData(self.width, self.id_wid)

    def ospec(self):
        return FPOpData(self.width, self.id_wid)

    def add_state(self, state):
        self.states.append(state)
        return state

    def get_fragment(self, platform=None):
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

        dn = self.add_state(FPAddDeNorm(self.width, self.id_wid))
        dn.setup(m, a, b, sc.in_mid)

        if self.single_cycle:
            alm = self.add_state(FPAddAlignSingle(self.width, self.id_wid))
            alm.setup(m, dn.out_a, dn.out_b, dn.in_mid)
        else:
            alm = self.add_state(FPAddAlignMulti(self.width, self.id_wid))
            alm.setup(m, dn.out_a, dn.out_b, dn.in_mid)

        add0 = self.add_state(FPAddStage0(self.width, self.id_wid))
        add0.setup(m, alm.out_a, alm.out_b, alm.in_mid)

        add1 = self.add_state(FPAddStage1(self.width, self.id_wid))
        add1.setup(m, add0.out_tot, add0.out_z, add0.in_mid)

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
        chain = StageChain(chainlist, specallocate=True)
        chain.setup(m, self.i)

        for mod in chainlist:
            sc = self.add_state(mod)

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
                     self.o.z.stb.eq(self.mod.o.z.stb),
                     self.mod.o.z.ack.eq(self.o.z.ack),
                    ]

        m.d.sync += self.add_stb.eq(add_stb)
        m.d.sync += self.add_ack.eq(0) # sets to zero when not in active state
        m.d.sync += self.o.z.ack.eq(0) # likewise
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
                             self.o.z.ack.eq(1),
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


class FPADDBasePipe(ControlBase):
    def __init__(self, width, id_wid):
        ControlBase.__init__(self)
        self.pipe1 = FPAddSpecialCasesDeNorm(width, id_wid)
        self.pipe2 = FPAddAlignSingleAdd(width, id_wid)
        self.pipe3 = FPNormToPack(width, id_wid)

        self._eqs = self.connect([self.pipe1, self.pipe2, self.pipe3])

    def elaborate(self, platform):
        m = Module()
        m.submodules.scnorm = self.pipe1
        m.submodules.addalign = self.pipe2
        m.submodules.normpack = self.pipe3
        m.d.comb += self._eqs
        return m


class FPADDInMuxPipe(PriorityCombMuxInPipe):
    def __init__(self, width, id_wid, num_rows):
        self.num_rows = num_rows
        def iospec(): return FPADDBaseData(width, id_wid)
        stage = PassThroughStage(iospec)
        PriorityCombMuxInPipe.__init__(self, stage, p_len=self.num_rows)


class FPADDMuxOutPipe(CombMuxOutPipe):
    def __init__(self, width, id_wid, num_rows):
        self.num_rows = num_rows
        def iospec(): return FPPackData(width, id_wid)
        stage = PassThroughStage(iospec)
        CombMuxOutPipe.__init__(self, stage, n_len=self.num_rows)


class FPADDMuxInOut:
    """ Reservation-Station version of FPADD pipeline.

        * fan-in on inputs (an array of FPADDBaseData: a,b,mid)
        * 3-stage adder pipeline
        * fan-out on outputs (an array of FPPackData: z,mid)

        Fan-in and Fan-out are combinatorial.
    """
    def __init__(self, width, id_wid, num_rows):
        self.num_rows = num_rows
        self.inpipe = FPADDInMuxPipe(width, id_wid, num_rows)   # fan-in
        self.fpadd = FPADDBasePipe(width, id_wid)               # add stage
        self.outpipe = FPADDMuxOutPipe(width, id_wid, num_rows) # fan-out

        self.p = self.inpipe.p  # kinda annoying,
        self.n = self.outpipe.n # use pipe in/out as this class in/out
        self._ports = self.inpipe.ports() + self.outpipe.ports()

    def elaborate(self, platform):
        m = Module()
        m.submodules.inpipe = self.inpipe
        m.submodules.fpadd = self.fpadd
        m.submodules.outpipe = self.outpipe

        m.d.comb += self.inpipe.n.connect_to_next(self.fpadd.p)
        m.d.comb += self.fpadd.connect_to_next(self.outpipe)

        return m

    def ports(self):
        return self._ports


class FPADD(FPID):
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
            in_a  = FPOp(width)
            in_b  = FPOp(width)
            in_a.name = "in_a_%d" % i
            in_b.name = "in_b_%d" % i
            rs.append((in_a, in_b))
        self.rs = Array(rs)

        res = []
        for i in range(rs_sz):
            out_z = FPOp(width)
            out_z.name = "out_z_%d" % i
            res.append(out_z)
        self.res = Array(res)

        self.states = []

    def add_state(self, state):
        self.states.append(state)
        return state

    def get_fragment(self, platform=None):
        """ creates the HDL code-fragment for FPAdd
        """
        m = Module()
        m.submodules += self.rs

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
