""" test of FPCVTMuxInOut
"""

from ieee754.fsgnj.pipeline import (FSGNJMuxInOut)
from ieee754.fpcommon.test.fpmux import runfp

import sfpy
from sfpy import Float64, Float32, Float16



######################
# signed int to fp
######################

def fsgnj_abs(x):
    return x.__abs__()

def test_fsgnj_abs():
    dut = FSGNJMuxInOut(32, 4)
    runfp(dut, 32, "test_fsgnj_abs", Float32, fsgnj_abs,
                True, n_vals=10, opcode=0x0)


if __name__ == '__main__':
    for i in range(200):
        test_fsgnj_abs()
