from nmigen import Elaboratable

class FPModBase(Elaboratable):
    """FPModBase: common code between nearly every pipeline module
    """
    def __init__(self, pspec, modname):
        self.modname = modname
        self.pspec = pspec
        self.i = self.ispec()
        self.o = self.ospec()

    def process(self, i):
        return self.o

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        setattr(m.submodules, self.modname, self)
        m.d.comb += self.i.eq(i)

