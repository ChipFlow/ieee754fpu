from ieee754.fpcommon.test.fpmux import runfp, repeat, pipe_cornercases_repeat

from random import randint
from random import seed

import sys

def corner_cases(mod):
    return [mod.zero(1), mod.zero(0),
            mod.inf(1), mod.inf(0),
            mod.nan(1), mod.nan(0)]

def get_corner_cases(mod):
    #corner cases
    from itertools import permutations
    cc = corner_cases(mod)
    stimulus_a = [i[0] for i in permutations(cc, 2)]
    stimulus_b = [i[1] for i in permutations(cc, 2)]
    return zip(stimulus_a, stimulus_b)


def replicate(fixed_num, maxcount):
    if isinstance(fixed_num, int):
        return [fixed_num for i in range(maxcount)]
    else:
        return fixed_num

def get_rval(width):
    mval = (1<<width)-1
    return randint(0, mval)

def get_rand1(mod, fixed_num, maxcount, width):
    stimulus_a = replicate(fixed_num, maxcount)
    stimulus_b = [get_rval(width) for i in range(maxcount)]
    yield from zip(stimulus_a, stimulus_b)
    yield from zip(stimulus_b, stimulus_a)


def get_nan_noncan(mod, fixed_num, maxcount, width):
    stimulus_a = replicate(fixed_num, maxcount)
    # non-canonical NaNs.
    stimulus_b = [mod.set_exponent(get_rval(width), mod.max_e) \
                        for i in range(maxcount)]
    yield from zip(stimulus_a, stimulus_b)
    yield from zip(stimulus_b, stimulus_a)


def get_n127(mod, fixed_num, maxcount, width):
    stimulus_a = replicate(fixed_num, maxcount)
    # -127
    stimulus_b = [mod.set_exponent(get_rval(width), -mod.max_e+1) \
                        for i in range(maxcount)]
    yield from zip(stimulus_a, stimulus_b)
    yield from zip(stimulus_b, stimulus_a)


def get_nearly_zero(mod, fixed_num, maxcount, width):
    stimulus_a = replicate(fixed_num, maxcount)
    # nearly zero
    stimulus_b = [mod.set_exponent(get_rval(width), -mod.max_e+2) \
                        for i in range(maxcount)]
    yield from zip(stimulus_a, stimulus_b)
    yield from zip(stimulus_b, stimulus_a)


def get_nearly_inf(mod, fixed_num, maxcount, width):
    stimulus_a = replicate(fixed_num, maxcount)
    # nearly inf
    stimulus_b = [mod.set_exponent(get_rval(width), mod.max_e-1) \
                        for i in range(maxcount)]
    yield from zip(stimulus_a, stimulus_b)
    yield from zip(stimulus_b, stimulus_a)


def get_corner_rand(mod, fixed_num, maxcount, width):
    stimulus_a = replicate(fixed_num, maxcount)
    # random
    stimulus_b = [get_rval(width) for i in range(maxcount)]
    yield from zip(stimulus_a, stimulus_b)
    yield from zip(stimulus_b, stimulus_a)


class PipeFPCase:
    def __init__(self, dut, name, mod, fmod, width, fpfn, count):
        self.dut = dut
        self.name = name
        self.mod = mod
        self.fmod = fmod
        self.width = width
        self.fpfn = fpfn
        self.count = count

    def run(self, name, fn):
        name = "%s_%s" % (self.name, name)
        pipe_cornercases_repeat(self.dut, name, self.mod, self.fmod,
                                self.width, fn, corner_cases, self.fpfn,
                                self.count)

    def run_cornercases(self):
        vals = repeat(self.dut.num_rows, get_corner_cases(self.mod))
        tname = "test_fp%s_pipe_fp%d_cornercases" % (self.name, self.width)
        runfp(self.dut, self.width, tname, self.fmod, self.fpfn, vals=vals)

    def run_regressions(self, regressions_fn):
        vals = repeat(self.dut.num_rows, regressions_fn())
        tname = "test_fp%s_pipe_fp%d_regressions" % (self.name, self.width)
        runfp(self.dut, self.width, tname, self.fmod, self.fpfn, vals=vals)

    def run_random(self):
        tname = "test_fp%s_pipe_fp%d_rand" % (self.name, self.width)
        runfp(self.dut, self.width, tname, self.fmod, self.fpfn)


def run_pipe_fp(dut, width, name, mod, fmod, regressions, fpfn, count):
    pc = PipeFPCase(dut, name, mod, fmod, width, fpfn, count)
    pc.run_regressions(regressions)
    pc.run_cornercases()
    pc.run("rand1", get_rand1)
    pc.run("n127", get_n127)
    pc.run("noncan", get_nan_noncan)
    pc.run("nearlyzero", get_nearly_zero)
    pc.run("nearlyinf", get_nearly_inf)
    pc.run("corner_rand", get_corner_rand)
    pc.run_random()

