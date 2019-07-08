from random import randint
from random import seed

import sys
from sfpy import Float32

corner_cases = [0x80000000, 0x00000000, 0x7f800000, 0xff800000,
                0x7fc00000, 0xffc00000]

def get_corner_cases(mod):
    #corner cases
    from itertools import permutations
    corner_cases = [mod.zero(1), mod.zero(0),
                    mod.inf(1), mod.inf(0),
                    mod.nan(1), mod.nan(0)]
    stimulus_a = [i[0] for i in permutations(corner_cases, 2)]
    stimulus_b = [i[1] for i in permutations(corner_cases, 2)]
    return zip(stimulus_a, stimulus_b)


def run_fpunit_2(dut, stimulus_a, stimulus_b, op, get_case_fn):
    yield from run_fpunit(dut, stimulus_a, stimulus_b, op, get_case_fn)
    yield from run_fpunit(dut, stimulus_b, stimulus_a, op, get_case_fn)

def run_cases(dut, count, op, fixed_num, maxcount, get_case_fn):
    if isinstance(fixed_num, int):
        stimulus_a = [fixed_num for i in range(maxcount)]
        report = hex(fixed_num)
    else:
        stimulus_a = fixed_num
        report = "random"

    stimulus_b = [randint(0, 1<<32) for i in range(maxcount)]
    yield from run_fpunit_2(dut, stimulus_a, stimulus_b, op, get_case_fn)
    count += len(stimulus_a)
    print (count, "vectors passed 2^32", report)

    # non-canonical NaNs.
    stimulus_b = [set_exponent(randint(0, 1<<32), 128) \
                        for i in range(maxcount)]
    yield from run_fpunit_2(dut, stimulus_a, stimulus_b, op, get_case_fn)
    count += len(stimulus_a)
    print (count, "vectors passed Non-Canonical NaN", report)

    # -127
    stimulus_b = [set_exponent(randint(0, 1<<32), -127) \
                        for i in range(maxcount)]
    yield from run_fpunit_2(dut, stimulus_a, stimulus_b, op, get_case_fn)
    count += len(stimulus_a)
    print (count, "vectors passed exp=-127", report)

    # nearly zero
    stimulus_b = [set_exponent(randint(0, 1<<32), -126) \
                        for i in range(maxcount)]
    yield from run_fpunit_2(dut, stimulus_a, stimulus_b, op, get_case_fn)
    count += len(stimulus_a)
    print (count, "vectors passed exp=-126", report)

    # nearly inf
    stimulus_b = [set_exponent(randint(0, 1<<32), 127) \
                        for i in range(maxcount)]
    yield from run_fpunit_2(dut, stimulus_a, stimulus_b, op, get_case_fn)
    count += len(stimulus_a)
    print (count, "vectors passed exp=127", report)

    return count

def run_edge_cases(dut, count, op, get_case_fn, maxcount=10, num_loops=1000):
    #edge cases
    for testme in corner_cases:
        count = yield from run_cases(dut, count, op, testme,
                                     maxcount, get_case_fn)

    for i in range(num_loops):
        stimulus_a = [randint(0, 1<<32) for i in range(maxcount)]
        count = yield from run_cases(dut, count, op, stimulus_a, 10,
                                     get_case_fn)
    return count

