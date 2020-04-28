from nmigen import Signal, Const
from nmutil.dynamicpipe import SimpleHandshakeRedir
import math


class CordicInitialData:

    def __init__(self, pspec):
        ZMAX = pspec.ZMAX
        self.z0 = Signal(range(-ZMAX, ZMAX), name="z")     # denormed result

    def __iter__(self):
        yield self.z0

    def eq(self, i):
        return [self.z0.eq(i.z0)]


class CordicData:

    def __init__(self, pspec):

        M = pspec.M
        ZMAX = pspec.ZMAX
        self.x = Signal(range(-M, M+1), name="x")   # operand a
        self.y = Signal(range(-M, M+1), name="y")   # operand b
        self.z = Signal(range(-ZMAX, ZMAX), name="z")     # denormed result

    def __iter__(self):
        yield self.x
        yield self.y
        yield self.z

    def eq(self, i):
        ret = [self.z.eq(i.z), self.x.eq(i.x), self.y.eq(i.y)]
        return ret


class CordicPipeSpec:
    def __init__(self, fracbits, rounds_per_stage):
        self.fracbits = fracbits
        # Number of cordic operations per pipeline stage
        self.rounds_per_stage = rounds_per_stage
        self.M = (1 << fracbits)
        self.ZMAX = int(round(self.M * math.pi/2))
        zm = Const(-self.ZMAX)
        self.iterations = zm.width - 1

        self.pipekls = SimpleHandshakeRedir
        self.stage = None