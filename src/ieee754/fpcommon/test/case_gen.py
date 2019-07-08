from random import randint
from random import seed

import sys
from sfpy import Float32

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


def get_rand1(mod, fixed_num, maxcount, width):
    stimulus_a = replicate(fixed_num, maxcount)
    stimulus_b = [randint(0, 1<<width) for i in range(maxcount)]
    return zip(stimulus_a, stimulus_b)


def get_nan_noncan(mod, fixed_num, maxcount, width):
    stimulus_a = replicate(fixed_num, maxcount)
    # non-canonical NaNs.
    stimulus_b = [mod.set_exponent(randint(0, 1<<width), mod.max_e) \
                        for i in range(maxcount)]
    return zip(stimulus_a, stimulus_b)


def get_n127(mod, fixed_num, maxcount, width):
    stimulus_a = replicate(fixed_num, maxcount)
    # -127
    stimulus_b = [mod.set_exponent(randint(0, 1<<width), -mod.max_e+1) \
                        for i in range(maxcount)]
    return zip(stimulus_a, stimulus_b)


def get_nearly_zero(mod, fixed_num, maxcount, width):
    stimulus_a = replicate(fixed_num, maxcount)
    # nearly zero
    stimulus_b = [mod.set_exponent(randint(0, 1<<width), -mod.max_e+2) \
                        for i in range(maxcount)]
    return zip(stimulus_a, stimulus_b)


def get_nearly_inf(mod, fixed_num, maxcount, width):
    stimulus_a = replicate(fixed_num, maxcount)
    # nearly inf
    stimulus_b = [mod.set_exponent(randint(0, 1<<width), mod.max_e-1) \
                        for i in range(maxcount)]
    return zip(stimulus_a, stimulus_b)


def get_corner_rand(mod, fixed_num, maxcount, width):
    stimulus_a = replicate(fixed_num, maxcount)
    # random
    stimulus_b = [randint(0, 1<<width) for i in range(maxcount)]
    return zip(stimulus_a, stimulus_b)

