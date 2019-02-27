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
Makefile:

    diff --git a/build/Linux-x86_64-GCC/Makefile b/build/Linux-x86_64-GCC/Makefile
    index 2ee5dad..566d225 100644
    --- a/build/Linux-x86_64-GCC/Makefile
    +++ b/build/Linux-x86_64-GCC/Makefile
    @@ -35,7 +35,7 @@
     #=============================================================================
     
     SOURCE_DIR ?= ../../source
    -SPECIALIZE_TYPE ?= 8086-SSE
    +SPECIALIZE_TYPE ?= RISCV
     
     SOFTFLOAT_OPTS ?= \
       -DSOFTFLOAT_ROUND_ODD -DINLINE_LEVEL=5 -DSOFTFLOAT_FAST_DIV32TO16 \
    @@ -45,7 +45,7 @@ DELETE = rm -f
     C_INCLUDES = -I. -I$(SOURCE_DIR)/$(SPECIALIZE_TYPE) -I$(SOURCE_DIR)/include
     COMPILE_C = \
       gcc -c -Werror-implicit-function-declaration -DSOFTFLOAT_FAST_INT64 \
    -    $(SOFTFLOAT_OPTS) $(C_INCLUDES) -O2 -o $@
    +    $(SOFTFLOAT_OPTS) $(C_INCLUDES) -O2 -fPIC -o $@
     MAKELIB = ar crs $@
     
     OBJ = .o


The following modifications are required to the sfpy SoftPosit Makefile:

    diff --git a/build/Linux-x86_64-GCC/Makefile b/build/Linux-x86_64-GCC/Makefile
    index 7affd4b..25dd39e 100644
    --- a/build/Linux-x86_64-GCC/Makefile
    +++ b/build/Linux-x86_64-GCC/Makefile
    @@ -69,7 +69,7 @@ endif
     C_INCLUDES = -I. -I$(SOURCE_DIR)/$(SPECIALIZE_TYPE) -I$(SOURCE_DIR)/include
     OPTIMISATION  = -O2 #-march=core-avx2
     COMPILE_C = \
    -  $(COMPILER) -c -Werror-implicit-function-declaration -DSOFTPOSIT_FAST_INT64 \
    +  $(COMPILER) -fPIC -c -Werror-implicit-function-declaration -DSOFTPOSIT_FAST_INT64 \
         $(SOFTPOSIT_OPTS) $(C_INCLUDES) $(OPTIMISATION) \
         -o $@ 
     MAKELIB = ar crs $@

# Useful resources

* https://en.wikipedia.org/wiki/IEEE_754-1985
* http://weitz.de/ieee/
* https://steve.hollasch.net/cgindex/coding/ieeefloat.html

