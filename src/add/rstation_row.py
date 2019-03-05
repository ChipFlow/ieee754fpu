from nmigen import Signal, Cat, Const, Mux, Module

from nmigen.cli import main, verilog

from fpbase import FPNumIn, FPNumOut, FPOp, Overflow, FPBase, FPNumBase
from fpbase import MultiShiftRMerge

class ReservationStationRow:

    def __init__(self, width, id_wid):
        """ Reservation Station row

            * width: bit-width of IEEE754.  supported: 16, 32, 64
            * id_wid: an identifier to be passed through to the FunctionUnit
        """
        self.width = width

        self.in_a  = Signal(width)
        self.in_b  = Signal(width)
        self.id_wid = id_wid
        self.out_z = Signal(width)

    def get_fragment(self, platform=None):
        """ creates the HDL code-fragment for ReservationStationRow
        """
        m = Module()

        return m


if __name__ == "__main__":
    rs = ReservationStationRow(width=32, id_wid=Const(1,4)
    main(alu, ports=[rs.in_a, rs.in_b, rs.out_z]

    # works... but don't use, just do "python fname.py convert -t v"
    #print (verilog.convert(alu, ports=[
    #                        ports=alu.in_a.ports() + \
    #                              alu.in_b.ports() + \
    #                              alu.out_z.ports())
