from nmigen import Elaboratable
from ieee754.pipeline import DynamicPipe
from nmutil.singlepipe import StageChain


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


class FPModBaseChain(DynamicPipe):
    """FPModBaseChain: common code between stage-chained pipes

    Links a set of combinatorial modules (get_chain) together
    and uses pspec.pipekls to dynamically select the pipeline type
    Also conforms to the Pipeline Stage API
    """
    def __init__(self, pspec):
        self.pspec = pspec
        self.chain = self.get_chain()
        super().__init__(pspec)

    def ispec(self):
        """ returns the input spec of the first module in the chain
        """
        return self.chain[0].ispec()

    def ospec(self):
        """ returns the output spec of the last module in the chain
        """
        return self.chain[-1].ospec()

    def process(self, i):
        return self.o # ... returned here (see setup comment below)

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        StageChain(self.chain).setup(m, i) # input linked here, through chain
        self.o = self.chain[-1].o # output is the last thing in the chain...
