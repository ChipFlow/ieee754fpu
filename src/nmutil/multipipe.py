""" Combinatorial Multi-input and Multi-output multiplexer blocks
    conforming to Pipeline API

    Multi-input is complex because if any one input is ready, the output
    can be ready, and the decision comes from a separate module.

    Multi-output is simple (pretty much identical to UnbufferedPipeline),
    and the selection is just a mux.  The only proviso (difference) being:
    the outputs not being selected have to have their ready_o signals
    DEASSERTED.
"""

from math import log
from nmigen import Signal, Cat, Const, Mux, Module, Array, Elaboratable
from nmigen.cli import verilog, rtlil
from nmigen.lib.coding import PriorityEncoder
from nmigen.hdl.rec import Record, Layout
from nmutil.stageapi import _spec

from collections.abc import Sequence

from .nmoperator import eq
from .iocontrol import NextControl, PrevControl


class MultiInControlBase(Elaboratable):
    """ Common functions for Pipeline API
    """
    def __init__(self, in_multi=None, p_len=1, maskwid=0, routemask=False):
        """ Multi-input Control class.  Conforms to same API as ControlBase...
            mostly.  has additional indices to the *multiple* input stages

            * p: contains ready/valid to the previous stages PLURAL
            * n: contains ready/valid to the next stage

            User must also:
            * add data_i members to PrevControl and
            * add data_o member  to NextControl
        """
        self.routemask = routemask
        # set up input and output IO ACK (prev/next ready/valid)
        print ("multi_in", maskwid, p_len)
        p = []
        for i in range(p_len):
            p.append(PrevControl(in_multi, maskwid=maskwid))
        self.p = Array(p)
        if routemask:
            nmaskwid = maskwid # straight route mask mode
        else:
            nmaskwid = maskwid * p_len # fan-in mode
        self.n = NextControl(maskwid=maskwid*p_len) # masks fan in (Cat)

    def connect_to_next(self, nxt, p_idx=0):
        """ helper function to connect to the next stage data/valid/ready.
        """
        return self.n.connect_to_next(nxt.p[p_idx])

    def _connect_in(self, prev, idx=0, prev_idx=None):
        """ helper function to connect stage to an input source.  do not
            use to connect stage-to-stage!
        """
        if prev_idx is None:
            return self.p[idx]._connect_in(prev.p)
        return self.p[idx]._connect_in(prev.p[prev_idx])

    def _connect_out(self, nxt):
        """ helper function to connect stage to an output source.  do not
            use to connect stage-to-stage!
        """
        if nxt_idx is None:
            return self.n._connect_out(nxt.n)
        return self.n._connect_out(nxt.n)

    def set_input(self, i, idx=0):
        """ helper function to set the input data
        """
        return eq(self.p[idx].data_i, i)

    def elaborate(self, platform):
        m = Module()
        for i, p in enumerate(self.p):
            setattr(m.submodules, "p%d" % i, p)
        m.submodules.n = self.n
        return m

    def __iter__(self):
        for p in self.p:
            yield from p
        yield from self.n

    def ports(self):
        return list(self)


class MultiOutControlBase(Elaboratable):
    """ Common functions for Pipeline API
    """
    def __init__(self, n_len=1, in_multi=None, maskwid=0, routemask=False):
        """ Multi-output Control class.  Conforms to same API as ControlBase...
            mostly.  has additional indices to the multiple *output* stages
            [MultiInControlBase has multiple *input* stages]

            * p: contains ready/valid to the previou stage
            * n: contains ready/valid to the next stages PLURAL

            User must also:
            * add data_i member to PrevControl and
            * add data_o members to NextControl
        """

        if routemask:
            nmaskwid = maskwid # straight route mask mode
        else:
            nmaskwid = maskwid * n_len # fan-out mode

        # set up input and output IO ACK (prev/next ready/valid)
        self.p = PrevControl(in_multi, maskwid=nmaskwid) 
        n = []
        for i in range(n_len):
            n.append(NextControl(maskwid=maskwid))
        self.n = Array(n)

    def connect_to_next(self, nxt, n_idx=0):
        """ helper function to connect to the next stage data/valid/ready.
        """
        return self.n[n_idx].connect_to_next(nxt.p)

    def _connect_in(self, prev, idx=0):
        """ helper function to connect stage to an input source.  do not
            use to connect stage-to-stage!
        """
        return self.n[idx]._connect_in(prev.p)

    def _connect_out(self, nxt, idx=0, nxt_idx=None):
        """ helper function to connect stage to an output source.  do not
            use to connect stage-to-stage!
        """
        if nxt_idx is None:
            return self.n[idx]._connect_out(nxt.n)
        return self.n[idx]._connect_out(nxt.n[nxt_idx])

    def elaborate(self, platform):
        m = Module()
        m.submodules.p = self.p
        for i, n in enumerate(self.n):
            setattr(m.submodules, "n%d" % i, n)
        return m

    def set_input(self, i):
        """ helper function to set the input data
        """
        return eq(self.p.data_i, i)

    def __iter__(self):
        yield from self.p
        for n in self.n:
            yield from n

    def ports(self):
        return list(self)


class CombMultiOutPipeline(MultiOutControlBase):
    """ A multi-input Combinatorial block conforming to the Pipeline API

        Attributes:
        -----------
        p.data_i : stage input data (non-array).  shaped according to ispec
        n.data_o : stage output data array.       shaped according to ospec
    """

    def __init__(self, stage, n_len, n_mux, maskwid=0, routemask=False):
        MultiOutControlBase.__init__(self, n_len=n_len, maskwid=maskwid,
                                            routemask=routemask)
        self.stage = stage
        self.maskwid = maskwid
        self.routemask = routemask
        self.n_mux = n_mux

        # set up the input and output data
        self.p.data_i = _spec(stage.ispec, 'data_i') # input type
        for i in range(n_len):
            name = 'data_o_%d' % i
            self.n[i].data_o = _spec(stage.ospec, name) # output type

    def process(self, i):
        if hasattr(self.stage, "process"):
            return self.stage.process(i)
        return i

    def elaborate(self, platform):
        m = MultiOutControlBase.elaborate(self, platform)

        if hasattr(self.n_mux, "elaborate"): # TODO: identify submodule?
            m.submodules.n_mux = self.n_mux

        # need buffer register conforming to *input* spec
        r_data = _spec(self.stage.ispec, 'r_data') # input type
        if hasattr(self.stage, "setup"):
            self.stage.setup(m, r_data)

        # multiplexer id taken from n_mux
        muxid = self.n_mux.m_id
        print ("self.n_mux", self.n_mux)
        print ("self.n_mux.m_id", self.n_mux.m_id)

        # temporaries
        p_valid_i = Signal(reset_less=True)
        pv = Signal(reset_less=True)
        m.d.comb += p_valid_i.eq(self.p.valid_i_test)
        m.d.comb += pv.eq(self.p.valid_i) #& self.n[muxid].ready_i)

        # all outputs to next stages first initialised to zero (invalid)
        # the only output "active" is then selected by the muxid
        for i in range(len(self.n)):
            m.d.comb += self.n[i].valid_o.eq(0)
        #with m.If(pv):
        m.d.comb += self.n[muxid].valid_o.eq(pv)
        m.d.comb += self.p.ready_o.eq(self.n[muxid].ready_i)

        # send data on
        #with m.If(pv):
        m.d.comb += eq(r_data, self.p.data_i)
        m.d.comb += eq(self.n[muxid].data_o, self.process(r_data))

        if self.maskwid:
            if self.routemask: # straight "routing" mode - treat like data
                m.d.comb += self.n[muxid].stop_o.eq(self.p.stop_i)
                #with m.If(pv):
                m.d.comb += self.n[muxid].mask_o.eq(self.p.mask_i)
            else:
                ml = [] # accumulate output masks
                ms = [] # accumulate output stops
                # fan-out mode.
                # conditionally fan-out mask bits, always fan-out stop bits
                for i in range(len(self.n)):
                    ml.append(self.n[i].mask_o)
                    ms.append(self.n[i].stop_o)
                m.d.comb += Cat(*ms).eq(self.p.stop_i)
                with m.If(pv):
                    m.d.comb += Cat(*ml).eq(self.p.mask_i)
        return m


class CombMultiInPipeline(MultiInControlBase):
    """ A multi-input Combinatorial block conforming to the Pipeline API

        Attributes:
        -----------
        p.data_i : StageInput, shaped according to ispec
            The pipeline input
        p.data_o : StageOutput, shaped according to ospec
            The pipeline output
        r_data : input_shape according to ispec
            A temporary (buffered) copy of a prior (valid) input.
            This is HELD if the output is not ready.  It is updated
            SYNCHRONOUSLY.
    """

    def __init__(self, stage, p_len, p_mux, maskwid=0, routemask=False):
        MultiInControlBase.__init__(self, p_len=p_len, maskwid=maskwid,
                                          routemask=routemask)
        self.stage = stage
        self.maskwid = maskwid
        self.p_mux = p_mux

        # set up the input and output data
        for i in range(p_len):
            name = 'data_i_%d' % i
            self.p[i].data_i = _spec(stage.ispec, name) # input type
        self.n.data_o = _spec(stage.ospec, 'data_o')

    def process(self, i):
        if hasattr(self.stage, "process"):
            return self.stage.process(i)
        return i

    def elaborate(self, platform):
        m = MultiInControlBase.elaborate(self, platform)

        m.submodules.p_mux = self.p_mux

        # need an array of buffer registers conforming to *input* spec
        r_data = []
        data_valid = []
        p_valid_i = []
        n_ready_in = []
        p_len = len(self.p)
        for i in range(p_len):
            name = 'r_%d' % i
            r = _spec(self.stage.ispec, name) # input type
            r_data.append(r)
            data_valid.append(Signal(name="data_valid", reset_less=True))
            p_valid_i.append(Signal(name="p_valid_i", reset_less=True))
            n_ready_in.append(Signal(name="n_ready_in", reset_less=True))
            if hasattr(self.stage, "setup"):
                print ("setup", self, self.stage, r)
                self.stage.setup(m, r)
        if len(r_data) > 1:
            r_data = Array(r_data)
            p_valid_i = Array(p_valid_i)
            n_ready_in = Array(n_ready_in)
            data_valid = Array(data_valid)

        nirn = Signal(reset_less=True)
        m.d.comb += nirn.eq(~self.n.ready_i)
        mid = self.p_mux.m_id
        print ("CombMuxIn mid", self, self.stage, self.routemask, mid, p_len)
        for i in range(p_len):
            m.d.comb += data_valid[i].eq(0)
            m.d.comb += n_ready_in[i].eq(1)
            m.d.comb += p_valid_i[i].eq(0)
            m.d.comb += self.p[i].ready_o.eq(0)
        m.d.comb += p_valid_i[mid].eq(self.p_mux.active)
        m.d.comb += self.p[mid].ready_o.eq(~data_valid[mid] | self.n.ready_i)
        m.d.comb += n_ready_in[mid].eq(nirn & data_valid[mid])
        anyvalid = Signal(i, reset_less=True)
        av = []
        for i in range(p_len):
            av.append(data_valid[i])
        anyvalid = Cat(*av)
        m.d.comb += self.n.valid_o.eq(anyvalid.bool())
        m.d.comb += data_valid[mid].eq(p_valid_i[mid] | \
                                    (n_ready_in[mid] & data_valid[mid]))

        if self.routemask:
            for i in range(p_len):
                p = self.p[i]
                vr = Signal(reset_less=True)
                maskedout = Signal(reset_less=True)
                m.d.comb += maskedout.eq(p.mask_i & ~p.stop_i)
                m.d.comb += vr.eq(maskedout.bool() & p.valid_i & p.ready_o)
                with m.If(vr):
                    m.d.comb += eq(self.n.mask_o, self.p[i].mask_i)
                    m.d.comb += eq(r_data[i], self.p[i].data_i)
                    m.d.comb += eq(self.n.stop_o, self.p[i].stop_i)
        else:
            ml = [] # accumulate output masks
            ms = [] # accumulate output stops
            for i in range(p_len):
                vr = Signal(reset_less=True)
                p = self.p[i]
                vr = Signal(reset_less=True)
                maskedout = Signal(reset_less=True)
                m.d.comb += maskedout.eq(p.mask_i & ~p.stop_i)
                m.d.comb += vr.eq(maskedout.bool() & p.valid_i & p.ready_o)
                with m.If(vr):
                    m.d.comb += eq(r_data[i], self.p[i].data_i)
                if self.maskwid:
                    mlen = len(self.p[i].mask_i)
                    s = mlen*i
                    e = mlen*(i+1)
                    ml.append(Mux(vr, self.p[i].mask_i, Const(0, mlen)))
                    ms.append(self.p[i].stop_i)
            if self.maskwid:
                m.d.comb += self.n.mask_o.eq(Cat(*ml))
                m.d.comb += self.n.stop_o.eq(Cat(*ms))

        m.d.comb += eq(self.n.data_o, self.process(r_data[mid]))

        return m


class CombMuxOutPipe(CombMultiOutPipeline):
    def __init__(self, stage, n_len, maskwid=0, muxidname=None,
                                     routemask=False):
        muxidname = muxidname or "muxid"
        # HACK: stage is also the n-way multiplexer
        CombMultiOutPipeline.__init__(self, stage, n_len=n_len,
                                            n_mux=stage, maskwid=maskwid,
                                            routemask=routemask)

        # HACK: n-mux is also the stage... so set the muxid equal to input muxid
        muxid = getattr(self.p.data_i, muxidname)
        print ("combmuxout", muxidname, muxid)
        stage.m_id = muxid



class InputPriorityArbiter(Elaboratable):
    """ arbitration module for Input-Mux pipe, baed on PriorityEncoder
    """
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
            p_valid_i = Signal(reset_less=True)
            if self.pipe.maskwid and not self.pipe.routemask:
                p = self.pipe.p[i]
                maskedout = Signal(reset_less=True)
                m.d.comb += maskedout.eq(p.mask_i & ~p.stop_i)
                m.d.comb += p_valid_i.eq(maskedout.bool() & p.valid_i_test)
            else:
                m.d.comb += p_valid_i.eq(self.pipe.p[i].valid_i_test)
            in_ready.append(p_valid_i)
        m.d.comb += pe.i.eq(Cat(*in_ready)) # array of input "valids"
        m.d.comb += self.active.eq(~pe.n)   # encoder active (one input valid)
        m.d.comb += self.m_id.eq(pe.o)       # output one active input

        return m

    def ports(self):
        return [self.m_id, self.active]



class PriorityCombMuxInPipe(CombMultiInPipeline):
    """ an example of how to use the combinatorial pipeline.
    """

    def __init__(self, stage, p_len=2, maskwid=0, routemask=False):
        p_mux = InputPriorityArbiter(self, p_len)
        CombMultiInPipeline.__init__(self, stage, p_len, p_mux,
                                     maskwid=maskwid, routemask=routemask)


if __name__ == '__main__':

    from nmutil.test.example_buf_pipe import ExampleStage
    dut = PriorityCombMuxInPipe(ExampleStage)
    vl = rtlil.convert(dut, ports=dut.ports())
    with open("test_combpipe.il", "w") as f:
        f.write(vl)
