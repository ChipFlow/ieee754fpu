"""creates fp numbers that are range-limited

to properly test FPtoFP (higher to lower) and FPtoINT (higher to lower)
it's no good having FP numbers that, statistically 99.99% of the time,
are going to be converted to INF (max of the int or float).

therefore, numbers need to be *specifically* generated that have a high
probability of being within the target range or just outside of it
"""

from random import randint
from sfpy import Float16, Float32, Float64

def create_ranged_float(fkls, mainwid, fracwid):
    """create a floating-point number

    range: +/- twice the bit-range
    fractional part: to ensure that there's plenty to play with
    """
    mainwid = 1<<mainwid
    fracwid = 1<<fracwid
    v = float(randint(0, mainwid) - mainwid/2)
    frac = float(randint(0, fracwid)-fracwid/2) / (fracwid/2)

    # deliberately do them separate in case of overflow.
    # if done as "fkls(v + frac)" it's not the same
    x = fkls(v) + fkls(frac)
    return x.bits

def create_int(fkls, intwid):
    """create a floating-point number to fit into an integer
    """
    return create_ranged_float(fkls, intwid+1, intwid+1)

