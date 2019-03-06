from nmigen import Signal, Cat, Const, Mux, Module, Array
from nmigen.cli import main, verilog

from nmigen_add_experiment import FPADD
from rstation_row import ReservationStationRow

from math import log

class FunctionUnit:

    def __init__(self, width, num_units):
        """ Function Unit

            * width: bit-width of IEEE754.  supported: 16, 32, 64
            * num_units: number of Reservation Stations
        """
        self.width = width

        fus = []
        bsz = int(log(width) / log(2))
        for i in range(num_units):
            mid = Const(i, bsz)
            rs = ReservationStationRow(width, mid)
            rs.name = "RS%d" % i
            fus.append(rs)
        self.fus = Array(fus)

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
