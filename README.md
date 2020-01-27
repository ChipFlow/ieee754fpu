# IEEE754 Floating-Point ALU, in nmigen

This project implements a pipelined IEEE754 floating-point ALU that
supports FP16, FP32 and FP64.  It is a general-purpose unit that
may be used in any project (not limited to one specific processor).

# Requirements

* nmigen
* yosys (latest git repository, required by nmigen)
* sfpy (running unit tests).  provides python bindings to berkeley softfloat-3

# Building sfpy

The standard sfpy will not work without being modified to the type of
IEEE754 FP emulation being tested.  This FPU is emulating RISC-V, and
there is some weirdness in x86 IEEE754 implementations when it comes
to FP16 non-canonical NaNs.

The following modifications are required to the sfpy berkeley-softfloat-3
submodule:

    cd /path/to/sfpy/berkeley-softfloat-3
    git apply /path/to/ieee754fpu/berkeley-softfloat.patch



The following modifications are required to the sfpy SoftPosit Makefile:

    cd /path/to/sfpy/SoftPosit
    git apply /path/to/ieee754fpu/SoftPosit.patch

# Useful resources

* https://en.wikipedia.org/wiki/IEEE_754-1985
* http://weitz.de/ieee/
* https://steve.hollasch.net/cgindex/coding/ieeefloat.html

