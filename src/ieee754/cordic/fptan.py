from nmigen import Module, Elaboratable, Signal, Cat, Mux
from nmigen.cli import rtlil
import math
from enum import Enum, unique

class CordicState(Enum):
    WAITING = 0
    RUNNING = 1


class CORDIC(Elaboratable):
    def __init__(self, fracbits):
        self.fracbits = fracbits
        self.M = M = (1<<fracbits)
        self.ZMAX = ZMAX = int(round(self.M * math.pi/2))

        # sin/cos output in 0.ffffff format
        self.cos = Signal(range(-M, M-1))
        self.sin = Signal(range(-M, M-1))
        # angle input
        self.z0 = Signal(range(-ZMAX, ZMAX), reset_less=True)

        # cordic start flag
        self.start = Signal(reset_less=True)
        # cordic done/ready for input
        self.ready = Signal()

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
        angles = [int(round(self.M*math.atan(2**(-i))))
                  for i in range(self.iterations)]

        x = Signal(self.sin.shape())
        y = Signal(self.sin.shape())
        z = Signal(self.z0.shape())
        dx = Signal(self.sin.shape())
        dy = Signal(self.sin.shape())
        dz = Signal(self.z0.shape())
        i = Signal(range(self.iterations))
        
        state = Signal(CordicState)

        with m.If(state == CordicState.WAITING):
            with m.If(self.start):
                sync += x.eq(X0)
                sync += y.eq(0)
                sync += z.eq(self.z0)
                sync += i.eq(0)
                sync += self.ready.eq(0)
                sync += state.eq(CordicState.RUNNING)
        with m.If(state == CordicState.RUNNING):
            sync += dx.eq(x >> i)
            sync += dx.eq(y >> i)

        return m
    def ports(self):
        return [self.cos, self.sin, self.z0,
                self.ready, self.start]

if __name__ == '__main__':
    dut = CORDIC(8)
    vl = rtlil.convert(dut, ports=dut.ports())
    with open("cordic.il", "w") as f:
        f.write(vl)

