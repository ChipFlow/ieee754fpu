# This is an unpipelined version of an sin/cos cordic, which will
# later be used to verify the operation of a pipelined version

# see http://bugs.libre-riscv.org/show_bug.cgi?id=208
from nmigen import Module, Elaboratable, Signal, Memory
from nmigen.cli import rtlil
import math
from enum import Enum, unique
from ieee754.fpcommon.fpbase import FPNumBaseRecord, FPNumDecode


@unique
class CordicState(Enum):
    WAITING = 0
    INIT = 1
    RUNNING = 2


class CordicROM(Elaboratable):
    def __init__(self, fracbits, iterations):
        self.fracbits = fracbits
        self.iterations = iterations

        M = 1 << fracbits
        self.addr = Signal(range(iterations))
        self.data = Signal(range(-M, M-1))

        angles = [int(round(M*math.atan(2**(-i))))
                  for i in range(self.iterations)]

        self.mem = Memory(width=self.data.width,
                          depth=self.iterations,
                          init=angles)

    def elaborate(self, platform):
        m = Module()
        m.submodules.rdport = rdport = self.mem.read_port()
        m.d.comb += rdport.addr.eq(self.addr)
        m.d.comb += self.data.eq(rdport.data)
        return m


class CORDIC(Elaboratable):
    def __init__(self, width):

        self.z0 = Signal(width, name="z0")
        self.z_record = FPNumBaseRecord(self.z0.width, m_extra=True)
        self.fracbits = 2 * self.z_record.m_width
        self.M = M = (1 << self.fracbits)
        self.ZMAX = int(round(self.M * math.pi/2))

        # sin/cos output in 0.ffffff format
        self.cos = Signal(range(-M, M+1), reset=0)
        self.sin = Signal(range(-M, M+1), reset=0)
        # angle input

        # cordic start flag
        self.start = Signal(reset_less=True)
        # cordic done/ready for input
        self.ready = Signal(reset=True)

        self.width = self.z0.width
        self.iterations = self.width - 1

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        sync = m.d.sync

        m.submodules.z_in = z_in = FPNumDecode(None, self.z_record)
        comb += z_in.v.eq(self.z0)

        z_fixed = Signal(range(-self.ZMAX, self.ZMAX-1),
                         reset_less=True)

        # Calculate initial amplitude?
        An = 1.0
        for i in range(self.iterations):
            An *= math.sqrt(1 + 2**(-2*i))

        X0 = int(round(self.M*1/An))
        x = Signal(self.sin.shape())
        y = Signal(self.sin.shape())
        z = Signal(z_fixed.shape())
        dx = Signal(self.sin.shape())
        dy = Signal(self.sin.shape())
        dz = Signal(z_fixed.shape())
        i = Signal(range(self.iterations))
        state = Signal(CordicState, reset=CordicState.WAITING)

        m.submodules.anglerom = anglerom = \
            CordicROM(self.fracbits, self.iterations)

        comb += dx.eq(y >> i)
        comb += dy.eq(x >> i)
        comb += dz.eq(anglerom.data)
        comb += self.cos.eq(x)
        comb += self.sin.eq(y)
        with m.If(state == CordicState.WAITING):
            with m.If(self.start):
                sync += state.eq(CordicState.INIT)
                sync += z_fixed.eq(z_in.m << (self.fracbits - z_in.rmw))
        with m.If(state == CordicState.INIT):
            sync += x.eq(X0)
            sync += y.eq(0)
            sync += z.eq(z_fixed)
            sync += i.eq(0)
            sync += state.eq(CordicState.RUNNING)
            sync += anglerom.addr.eq(1)
        with m.If(state == CordicState.RUNNING):
            with m.If(z >= 0):
                sync += x.eq(x - dx)
                sync += y.eq(y + dy)
                sync += z.eq(z - dz)
            with m.Else():
                sync += x.eq(x + dx)
                sync += y.eq(y - dy)
                sync += z.eq(z + dz)
            with m.If(i == self.iterations - 1):
                sync += state.eq(CordicState.WAITING)
                sync += self.ready.eq(1)
                sync += anglerom.addr.eq(0)
            with m.Else():
                sync += i.eq(i+1)
                sync += anglerom.addr.eq(i+2)
        return m

    def ports(self):
        lst = [self.cos, self.sin,
               self.ready, self.start]
        lst.extend(self.z0)
        return lst


if __name__ == '__main__':
    dut = CORDIC(8)
    vl = rtlil.convert(dut, ports=dut.ports())
    with open("cordic.il", "w") as f:
        f.write(vl)
