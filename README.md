# IEEE754 Floating-Point ALU, in nmigen

This project implements a pipelined IEEE754 floating-point ALU that
supports FP16, FP32 and FP64.  It is a general-purpose unit that
may be used in any project (not limited to one specific processor).

# Requirements

* nmigen
* yosys (latest git repository, required by nmigen)
* sfpy (running unit tests).  provides python bindings to berkeley softfloat-3

# Useful resources

* https://en.wikipedia.org/wiki/IEEE_754-1985
* http://weitz.de/ieee/
* https://steve.hollasch.net/cgindex/coding/ieeefloat.html
