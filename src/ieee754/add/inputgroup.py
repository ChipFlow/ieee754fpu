from nmigen import Module, Signal, Cat, Array, Const
from nmigen.lib.coding import PriorityEncoder
from math import log

from ieee754.fpcommon.fpbase import Trigger


class FPGetSyncOpsMod:
    def __init__(self, width, num_ops=2):
        self.width = width
        self.num_ops = num_ops
        inops = []
        outops = []
        for i in range(num_ops):
            inops.append(Signal(width, reset_less=True))
            outops.append(Signal(width, reset_less=True))
        self.in_op = inops
        self.out_op = outops
        self.stb = Signal(num_ops)
        self.ack = Signal()
        self.ready = Signal(reset_less=True)
        self.out_decode = Signal(reset_less=True)

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.ready.eq(self.stb == Const(-1, (self.num_ops, False)))
        m.d.comb += self.out_decode.eq(self.ack & self.ready)
        with m.If(self.out_decode):
            for i in range(self.num_ops):
                m.d.comb += [
                        self.out_op[i].eq(self.in_op[i]),
                ]
        return m

    def ports(self):
        return self.in_op + self.out_op + [self.stb, self.ack]


class FPOps(Trigger):
    def __init__(self, width, num_ops):
        Trigger.__init__(self)
        self.width = width
        self.num_ops = num_ops

        res = []
        for i in range(num_ops):
            res.append(Signal(width))
        self.v  = Array(res)

    def ports(self):
        res = []
        for i in range(self.num_ops):
            res.append(self.v[i])
        res.append(self.ack)
        res.append(self.stb)
        return res


class InputGroup:
    def __init__(self, width, num_ops=2, num_rows=4):
        self.width = width
        self.num_ops = num_ops
        self.num_rows = num_rows
        self.mmax = int(log(self.num_rows) / log(2))
        self.rs = []
        self.muxid = Signal(self.mmax, reset_less=True) # multiplex id
        for i in range(num_rows):
            self.rs.append(FPGetSyncOpsMod(width, num_ops))
        self.rs = Array(self.rs)

        self.out_op = FPOps(width, num_ops)

    def elaborate(self, platform):
        m = Module()

        pe = PriorityEncoder(self.num_rows)
        m.submodules.selector = pe
        m.submodules.out_op = self.out_op
        m.submodules += self.rs

        # connect priority encoder
        in_ready = []
        for i in range(self.num_rows):
            in_ready.append(self.rs[i].ready)
        m.d.comb += pe.i.eq(Cat(*in_ready))

        active = Signal(reset_less=True)
        out_en = Signal(reset_less=True)
        m.d.comb += active.eq(~pe.n) # encoder active
        m.d.comb += out_en.eq(active & self.out_op.trigger)

        # encoder active: ack relevant input, record MID, pass output
        with m.If(out_en):
            rs = self.rs[pe.o]
            m.d.sync += self.muxid.eq(pe.o)
            m.d.sync += rs.ack.eq(0)
            m.d.sync += self.out_op.stb.eq(0)
            for j in range(self.num_ops):
                m.d.sync += self.out_op.v[j].eq(rs.out_op[j])
        with m.Else():
            m.d.sync += self.out_op.stb.eq(1)
            # acks all default to zero
            for i in range(self.num_rows):
                m.d.sync += self.rs[i].ack.eq(1)

        return m

    def ports(self):
        res = []
        for i in range(self.num_rows):
            inop = self.rs[i]
            res += inop.in_op + [inop.stb]
        return self.out_op.ports() + res + [self.muxid]


