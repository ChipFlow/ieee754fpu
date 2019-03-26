""" Combinatorial Multi-input multiplexer block conforming to Pipeline API
"""

from math import log
from nmigen import Signal, Cat, Const, Mux, Module, Array
from nmigen.cli import verilog, rtlil
from nmigen.lib.coding import PriorityEncoder
from nmigen.hdl.rec import Record, Layout

from collections.abc import Sequence

from example_buf_pipe import eq, NextControl, PrevControl, ExampleStage


class PipelineBase:
    """ Common functions for Pipeline API
    """
    def __init__(self, stage, in_multi=None, p_len=1):
        """ pass in a "stage" which may be either a static class or a class
            instance, which has four functions (one optional):
            * ispec: returns input signals according to the input specification
            * ispec: returns output signals to the output specification
            * process: takes an input instance and returns processed data
            * setup: performs any module linkage if the stage uses one.

            User must also:
            * add i_data member to PrevControl and
            * add o_data member to NextControl
        """
        self.stage = stage

        # set up input and output IO ACK (prev/next ready/valid)
        p = []
        for i in range(p_len):
            p.append(PrevControl(in_multi))
        self.p = Array(p)
        self.n = NextControl()

    def connect_to_next(self, nxt, p_idx=0):
        """ helper function to connect to the next stage data/valid/ready.
        """
        return self.n.connect_to_next(nxt.p[p_idx])

    def connect_in(self, prev, idx=0, prev_idx=None):
        """ helper function to connect stage to an input source.  do not
            use to connect stage-to-stage!
        """
        if prev_idx is None:
            return self.p[idx].connect_in(prev.p)
        return self.p[idx].connect_in(prev.p[prev_idx])

    def connect_out(self, nxt):
        """ helper function to connect stage to an output source.  do not
            use to connect stage-to-stage!
        """
        if nxt_idx is None:
            return self.n.connect_out(nxt.n)
        return self.n.connect_out(nxt.n)

    def set_input(self, i, idx=0):
        """ helper function to set the input data
        """
        return eq(self.p[idx].i_data, i)

    def ports(self):
        res = []
        for i in range(len(self.p)):
            res += [self.p[i].i_valid, self.p[i].o_ready,
                    self.p[i].i_data]# XXX need flattening!]
        res += [self.n.i_ready, self.n.o_valid,
                self.n.o_data]   # XXX need flattening!]
        return res



class CombMultiInPipeline(PipelineBase):
    """ A multi-input Combinatorial block conforming to the Pipeline API

        Attributes:
        -----------
        p.i_data : StageInput, shaped according to ispec
            The pipeline input
        p.o_data : StageOutput, shaped according to ospec
            The pipeline output
        r_data : input_shape according to ispec
            A temporary (buffered) copy of a prior (valid) input.
            This is HELD if the output is not ready.  It is updated
            SYNCHRONOUSLY.
    """

    def __init__(self, stage, p_len, p_mux):
        PipelineBase.__init__(self, stage, p_len=p_len)
        self.p_mux = p_mux

        # set up the input and output data
        for i in range(p_len):
            self.p[i].i_data = stage.ispec() # input type
        self.n.o_data = stage.ospec()

    def elaborate(self, platform):
        m = Module()

        m.submodules += self.p_mux

        # need an array of buffer registers conforming to *input* spec
        r_data = []
        data_valid = []
        p_i_valid = []
        n_i_readyn = []
        p_len = len(self.p)
        for i in range(p_len):
            r = self.stage.ispec() # input type
            r_data.append(r)
            data_valid.append(Signal(name="data_valid", reset_less=True))
            p_i_valid.append(Signal(name="p_i_valid", reset_less=True))
            n_i_readyn.append(Signal(name="n_i_readyn", reset_less=True))
            if hasattr(self.stage, "setup"):
                self.stage.setup(m, r)
        if len(r_data) > 1:
            r_data = Array(r_data)
            p_i_valid = Array(p_i_valid)
            n_i_readyn = Array(n_i_readyn)
            data_valid = Array(data_valid)

        mid = self.p_mux.m_id
        for i in range(p_len):
            m.d.comb += data_valid[i].eq(0)
            m.d.comb += n_i_readyn[i].eq(1)
            m.d.comb += p_i_valid[i].eq(0)
            m.d.comb += self.p[i].o_ready.eq(0)
        m.d.comb += p_i_valid[mid].eq(self.p_mux.active)
        m.d.comb += self.p[mid].o_ready.eq(~data_valid[mid] | self.n.i_ready)
        m.d.comb += n_i_readyn[mid].eq(~self.n.i_ready & data_valid[mid])
        anyvalid = Signal(i, reset_less=True)
        av = []
        for i in range(p_len):
            av.append(data_valid[i])
        anyvalid = Cat(*av)
        m.d.comb += self.n.o_valid.eq(anyvalid.bool())
        m.d.comb += data_valid[mid].eq(p_i_valid[mid] | \
                                    (n_i_readyn[mid] & data_valid[mid]))

        for i in range(p_len):
            vr = Signal(reset_less=True)
            m.d.comb += vr.eq(self.p[i].i_valid & self.p[i].o_ready)
            with m.If(vr):
                m.d.comb += eq(r_data[i], self.p[i].i_data)

        m.d.comb += eq(self.n.o_data, self.stage.process(r_data[mid]))

        return m


class InputPriorityArbiter:
    def __init__(self, pipe, num_rows):
        self.pipe = pipe
        self.num_rows = num_rows
        self.mmax = int(log(self.num_rows) / log(2))
        self.m_id = Signal(self.mmax, reset_less=True) # multiplex id
        self.active = Signal(reset_less=True)

    def elaborate(self, platform):
        m = Module()

        assert len(self.pipe.p) == self.num_rows, \
                "must declare input to be same size"
        pe = PriorityEncoder(self.num_rows)
        m.submodules.selector = pe

        # connect priority encoder
        in_ready = []
        for i in range(self.num_rows):
            p_i_valid = Signal(reset_less=True)
            m.d.comb += p_i_valid.eq(self.pipe.p[i].i_valid_logic())
            in_ready.append(p_i_valid)
        m.d.comb += pe.i.eq(Cat(*in_ready)) # array of input "valids"
        m.d.comb += self.active.eq(~pe.n)   # encoder active (one input valid)
        m.d.comb += self.m_id.eq(pe.o)       # output one active input

        return m

    def ports(self):
        return [self.m_id, self.active]



class ExamplePipeline(CombMultiInPipeline):
    """ an example of how to use the combinatorial pipeline.
    """

    def __init__(self, p_len=2):
        p_mux = InputPriorityArbiter(self, p_len)
        CombMultiInPipeline.__init__(self, ExampleStage, p_len, p_mux)


if __name__ == '__main__':

    dut = ExamplePipeline()
    vl = rtlil.convert(dut, ports=dut.ports())
    with open("test_combpipe.il", "w") as f:
        f.write(vl)
