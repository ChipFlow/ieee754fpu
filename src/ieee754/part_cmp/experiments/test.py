from ieee754.part_mul_add.partpoints import PartitionPoints
import ieee754.part_cmp.equal_ortree as ortree
import ieee754.part_cmp.equal as equal
from nmigen.cli import rtlil
from nmigen import Signal, Module

def create_ilang(mod, name, ports):
    vl = rtlil.convert(mod, ports=ports)
    with open(name, "w") as f:
        f.write(vl)

def create_ortree(width, points):
    sig = Signal(len(points.values()))
    for i, key in enumerate(points):
        points[key] = sig[i]
    eq = ortree.PartitionedEq(width, points)

    create_ilang(eq, "ortree.il", [eq.a, eq.b, eq.output, sig])

def create_equal(width, points):
    sig = Signal(len(points.values()))
    for i, key in enumerate(points):
        points[key] = sig[i]
    
    eq = equal.PartitionedEq(width, points)

    create_ilang(eq, "equal.il", [eq.a, eq.b, eq.output, sig])
    

if __name__ == "__main__":
    points = PartitionPoints()
    sig = Signal(7)
    for i in range(sig.width):
        points[i*8+8] = True

    # create_equal(32, points)
    create_ortree(64, points)





# ortree:
# === design hierarchy ===

   # top                               1
   #   mux1                            1
   #   mux2                            1
   #   mux3                            1

   # Number of wires:                 49
   # Number of wire bits:             89
   # Number of public wires:          36
   # Number of public wire bits:      76
   # Number of memories:               0
   # Number of memory bits:            0
   # Number of processes:              0
   # Number of cells:                 29
   #   $_MUX_                          6
   #   $_NOR_                          1
   #   $_NOT_                          3
   #   $_OR_                           8
   #   $_XOR_                         11


# equals:
# === top ===

#    Number of wires:                121
#    Number of wire bits:            161
#    Number of public wires:          12
#    Number of public wire bits:      52
#    Number of memories:               0
#    Number of memory bits:            0
#    Number of processes:              0
#    Number of cells:                113
#      $_ANDNOT_                      32
#      $_AND_                          7
#      $_MUX_                          4
#      $_NAND_                         1
#      $_NOR_                          2
#      $_NOT_                          1
#      $_ORNOT_                        6
#      $_OR_                          44
#      $_XNOR_                         1
#      $_XOR_                         15
