# This is an unpipelined version of an sin/cos cordic, which will
# later be used to verify the operation of a pipelined version

# see http://bugs.libre-riscv.org/show_bug.cgi?id=208
from nmigen import (Module, Elaboratable, Signal, Memory,
                    Cat, Repl, Mux, signed)
from nmigen.cli import rtlil
import math
from enum import Enum, unique
from ieee754.fpcommon.fpbase import FPNumBaseRecord, FPNumDecode
import bigfloat as bf
from bigfloat import BigFloat


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
        self.data = Signal(signed(fracbits + 2))

        angles = []
        with bf.quadruple_precision:
            for i in range(self.iterations):
                x = bf.atan(BigFloat(2) ** BigFloat(-i))
                x = x/(bf.const_pi()/2)
                x = x * M
                angles.append(int(round(x)))

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
        self.z_record = FPNumBaseRecord(self.z0.width, False, name="z_record")
        self.fracbits = 2 * self.z_record.m_width
        self.M = M = (1 << self.fracbits)
        self.ZMAX = int(round(self.M * math.pi/2))

        self.z_out = Signal(signed(self.fracbits + 2))

        # sin/cos output in 0.ffffff format
        self.cos = Signal(signed(self.fracbits + 2), reset=0)
        self.sin = Signal(signed(self.fracbits + 2), reset=0)
        # angle input

        # cordic start flag
        self.start = Signal(reset_less=True)
        # cordic done/ready for input
        self.ready = Signal(reset=True)

        self.width = self.z0.width
        self.iterations = self.fracbits - 1

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        sync = m.d.sync

        m.submodules.z_in = z_in = FPNumDecode(None, self.z_record)
        comb += z_in.v.eq(self.z0)

        z_fixed = Signal(signed(self.fracbits + 2),
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
                z_intermed = Signal(z_fixed.shape())
                shifter = Signal(z_in.e.width)
                comb += shifter.eq(-z_in.e)
                # This converts z_in.m to a large fixed point
                # integer. Right now, I'm ignoring denormals but they
                # will be added back in when I convert this to the
                # pipelined implementation (and I can use FPAddDenormMod)
                comb += z_intermed.eq(Cat(Repl(0, self.fracbits - z_in.rmw),
                                          z_in.m[:-1], 1))
                sync += z_fixed.eq(z_intermed >> shifter)
                sync += state.eq(CordicState.INIT)
                sync += self.ready.eq(0)
        with m.If(state == CordicState.INIT):
            z_temp = Signal(z.shape(), reset_less=True)
            comb += z_temp.eq(Mux(z_in.s, ~z_fixed + 1, z_fixed))
            sync += z.eq(z_temp)
            sync += self.z_out.eq(z_temp)
            sync += x.eq(X0)
            sync += y.eq(0)
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
        return [self.cos, self.sin,
               self.ready, self.start,
               self.z0]


if __name__ == '__main__':
    dut = CORDIC(16)
    vl = rtlil.convert(dut, ports=dut.ports())
    with open("cordic.il", "w") as f:
        f.write(vl)
