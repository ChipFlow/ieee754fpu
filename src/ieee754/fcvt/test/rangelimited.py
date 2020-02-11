"""creates fp numbers that are range-limited

to properly test FPtoFP (higher to lower) and FPtoINT (higher to lower)
it's no good having FP numbers that, statistically 99.99% of the time,
are going to be converted to INF (max of the int or float).

therefore, numbers need to be *specifically* generated that have a high
probability of being within the target range or just outside of it
"""

from random import randint
from sfpy import Float16, Float32, Float64

def create_ranged_target(fkls, target):
    """create a targetted floating-point number just within
       the min/max range, by +/- 0.5%
    """
    if randint(0, 1) == 1:
        target = -target
    res = fkls(target)
    fracwid = 1<<50 # biiig number...
    frac = float(randint(0, fracwid)-fracwid/2) / (fracwid/2) # +/- 0.99999
    frac = (frac + 500.0) / 500.0 # change to 0.1%
    res = res * fkls(frac)

    return res.bits

def create_ranged_fp16(fkls):
    return create_ranged_target(fkls, 65519.0)

def create_ranged_fp32(fkls):
    return create_ranged_target(fkls, 3.402823466E38)

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

if __name__ == '__main__':
    for i in range(10):
        x = create_ranged_fp16(Float32)
        print (Float32(x))
        x = Float32(x)
        print (Float16(x))
    for i in range(10):
        x = create_ranged_fp32(Float64)
        print (Float64(x))
        x = Float64(x)
        print (Float32(x))
