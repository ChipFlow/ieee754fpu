from nmigen import Module, Elaboratable, Signal, Memory, signed
from nmigen.cli import rtlil
import math
from enum import Enum, unique


@unique
class CordicState(Enum):
    WAITING = 0
    RUNNING = 1


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
    def __init__(self, fracbits):
        self.fracbits = fracbits
        self.M = M = (1 << fracbits)
        self.ZMAX = ZMAX = int(round(self.M * math.pi/2))

        # sin/cos output in 0.ffffff format
        self.cos = Signal(range(-M, M-1), reset=0)
        self.sin = Signal(range(-M, M-1), reset=0)
        # angle input
        self.z0 = Signal(range(-ZMAX, ZMAX), reset_less=True)

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


        # Calculate initial amplitude?
        An = 1.0
        for i in range(self.iterations):
            An *= math.sqrt(1 + 2**(-2*i))

        X0 = int(round(self.M*1/An))
        x = Signal(self.sin.shape())
        y = Signal(self.sin.shape())
        z = Signal(self.z0.shape())
        dx = Signal(self.sin.shape())
        dy = Signal(self.sin.shape())
        dz = Signal(self.z0.shape())
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
                sync += x.eq(X0)
                sync += y.eq(0)
                sync += z.eq(self.z0)
                sync += i.eq(0)
                sync += self.ready.eq(0)
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
            with m.Else():
                sync += i.eq(i+1)
                sync += anglerom.addr.eq(i+2)
        return m

    def ports(self):
        return [self.cos, self.sin, self.z0,
                self.ready, self.start]

if __name__ == '__main__':
    dut = CORDIC(8)
    vl = rtlil.convert(dut, ports=dut.ports())
    with open("cordic.il", "w") as f:
        f.write(vl)

