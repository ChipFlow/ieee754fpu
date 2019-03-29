# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen.cli import main, verilog
from fpadd.statemachine import FPADDBase, FPADD
from fpadd.pipeline import FPADDMuxInOut

if __name__ == "__main__":
    if True:
        alu = FPADD(width=32, id_wid=5, single_cycle=True)
        main(alu, ports=alu.rs[0][0].ports() + \
                        alu.rs[0][1].ports() + \
                        alu.res[0].ports() + \
                        [alu.ids.in_mid, alu.ids.out_mid])
    else:
        alu = FPADDBase(width=32, id_wid=5, single_cycle=True)
        main(alu, ports=[alu.in_a, alu.in_b] + \
                        alu.in_t.ports() + \
                        alu.out_z.ports() + \
                        [alu.in_mid, alu.out_mid])


    # works... but don't use, just do "python fname.py convert -t v"
    #print (verilog.convert(alu, ports=[
    #                        ports=alu.in_a.ports() + \
    #                              alu.in_b.ports() + \
    #                              alu.out_z.ports())
