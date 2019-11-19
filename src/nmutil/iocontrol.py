""" IO Control API

    Associated development bugs:
    * http://bugs.libre-riscv.org/show_bug.cgi?id=148
    * http://bugs.libre-riscv.org/show_bug.cgi?id=64
    * http://bugs.libre-riscv.org/show_bug.cgi?id=57

    Important: see Stage API (stageapi.py) in combination with below

    Main classes: PrevControl and NextControl.

    These classes manage the data and the synchronisation state
    to the previous and next stage, respectively.  ready/valid
    signals are used by the Pipeline classes to tell if data
    may be safely passed from stage to stage.

    The connection from one stage to the next is carried out with
    NextControl.connect_to_next.  It is *not* necessary to have
    a PrevControl.connect_to_prev because it is functionally
    directly equivalent to prev->next->connect_to_next.
"""

from nmigen import Signal, Cat, Const, Module, Value, Elaboratable
from nmigen.cli import verilog, rtlil
from nmigen.hdl.rec import Record

from collections.abc import Sequence, Iterable
from collections import OrderedDict

from nmutil import nmoperator


class Object:
    def __init__(self):
        self.fields = OrderedDict()

    def __setattr__(self, k, v):
        print ("kv", k, v)
        if (k.startswith('_') or k in ["fields", "name", "src_loc"] or
           k in dir(Object) or "fields" not in self.__dict__):
            return object.__setattr__(self, k, v)
        self.fields[k] = v

    def __getattr__(self, k):
        if k in self.__dict__:
            return object.__getattr__(self, k)
        try:
            return self.fields[k]
        except KeyError as e:
            raise AttributeError(e)

    def __iter__(self):
        for x in self.fields.values():  # OrderedDict so order is preserved
            if isinstance(x, Iterable):
                yield from x
            else:
                yield x

    def eq(self, inp):
        res = []
        for (k, o) in self.fields.items():
            i = getattr(inp, k)
            print ("eq", o, i)
            rres = o.eq(i)
            if isinstance(rres, Sequence):
                res += rres
            else:
                res.append(rres)
        print (res)
        return res

    def ports(self): # being called "keys" would be much better
        return list(self)


class RecordObject(Record):
    def __init__(self, layout=None, name=None):
        Record.__init__(self, layout=layout or [], name=name)

    def __setattr__(self, k, v):
        #print (dir(Record))
        if (k.startswith('_') or k in ["fields", "name", "src_loc"] or
           k in dir(Record) or "fields" not in self.__dict__):
            return object.__setattr__(self, k, v)
        self.fields[k] = v
        #print ("RecordObject setattr", k, v)
        if isinstance(v, Record):
            newlayout = {k: (k, v.layout)}
        elif isinstance(v, Value):
            newlayout = {k: (k, v.shape())}
        else:
            newlayout = {k: (k, nmoperator.shape(v))}
        self.layout.fields.update(newlayout)

    def __iter__(self):
        for x in self.fields.values(): # remember: fields is an OrderedDict
            if isinstance(x, Iterable):
                yield from x           # a bit like flatten (nmigen.tools)
            else:
                yield x

    def ports(self): # would be better being called "keys"
        return list(self)


class PrevControl(Elaboratable):
    """ contains signals that come *from* the previous stage (both in and out)
        * valid_i: previous stage indicating all incoming data is valid.
                   may be a multi-bit signal, where all bits are required
                   to be asserted to indicate "valid".
        * ready_o: output to next stage indicating readiness to accept data
        * data_i : an input - MUST be added by the USER of this class
    """

    def __init__(self, i_width=1, stage_ctl=False, maskwid=0, offs=0):
        self.stage_ctl = stage_ctl
        self.maskwid = maskwid
        if maskwid:
            self.mask_i = Signal(maskwid)                # prev   >>in  self
            self.stop_i = Signal(maskwid)                # prev   >>in  self
        self.valid_i = Signal(i_width, name="p_valid_i") # prev   >>in  self
        self._ready_o = Signal(name="p_ready_o")         # prev   <<out self
        self.data_i = None # XXX MUST BE ADDED BY USER
        if stage_ctl:
            self.s_ready_o = Signal(name="p_s_o_rdy")    # prev   <<out self
        self.trigger = Signal(reset_less=True)

    @property
    def ready_o(self):
        """ public-facing API: indicates (externally) that stage is ready
        """
        if self.stage_ctl:
            return self.s_ready_o # set dynamically by stage
        return self._ready_o      # return this when not under dynamic control

    def _connect_in(self, prev, direct=False, fn=None,
                    do_data=True, do_stop=True):
        """ internal helper function to connect stage to an input source.
            do not use to connect stage-to-stage!
        """
        valid_i = prev.valid_i if direct else prev.valid_i_test
        res = [self.valid_i.eq(valid_i),
               prev.ready_o.eq(self.ready_o)]
        if self.maskwid:
            res.append(self.mask_i.eq(prev.mask_i))
            if do_stop:
                res.append(self.stop_i.eq(prev.stop_i))
        if do_data is False:
            return res
        data_i = fn(prev.data_i) if fn is not None else prev.data_i
        return res + [nmoperator.eq(self.data_i, data_i)]

    @property
    def valid_i_test(self):
        vlen = len(self.valid_i)
        if vlen > 1:
            # multi-bit case: valid only when valid_i is all 1s
            all1s = Const(-1, (len(self.valid_i), False))
            valid_i = (self.valid_i == all1s)
        else:
            # single-bit valid_i case
            valid_i = self.valid_i

        # when stage indicates not ready, incoming data
        # must "appear" to be not ready too
        if self.stage_ctl:
            valid_i = valid_i & self.s_ready_o

        return valid_i

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.trigger.eq(self.valid_i_test & self.ready_o)
        return m

    def eq(self, i):
        res = [nmoperator.eq(self.data_i, i.data_i),
                self.ready_o.eq(i.ready_o),
                self.valid_i.eq(i.valid_i)]
        if self.maskwid:
            res.append(self.mask_i.eq(i.mask_i))
        return res

    def __iter__(self):
        yield self.valid_i
        yield self.ready_o
        if self.maskwid:
            yield self.mask_i
            yield self.stop_i
        if hasattr(self.data_i, "ports"):
            yield from self.data_i.ports()
        elif isinstance(self.data_i, Sequence):
            yield from self.data_i
        else:
            yield self.data_i

    def ports(self):
        return list(self)


class NextControl(Elaboratable):
    """ contains the signals that go *to* the next stage (both in and out)
        * valid_o: output indicating to next stage that data is valid
        * ready_i: input from next stage indicating that it can accept data
        * data_o : an output - MUST be added by the USER of this class
    """
    def __init__(self, stage_ctl=False, maskwid=0):
        self.stage_ctl = stage_ctl
        self.maskwid = maskwid
        if maskwid:
            self.mask_o = Signal(maskwid)       # self out>>  next
            self.stop_o = Signal(maskwid)       # self out>>  next
        self.valid_o = Signal(name="n_valid_o") # self out>>  next
        self.ready_i = Signal(name="n_ready_i") # self <<in   next
        self.data_o = None # XXX MUST BE ADDED BY USER
        #if self.stage_ctl:
        self.d_valid = Signal(reset=1) # INTERNAL (data valid)
        self.trigger = Signal(reset_less=True)

    @property
    def ready_i_test(self):
        if self.stage_ctl:
            return self.ready_i & self.d_valid
        return self.ready_i

    def connect_to_next(self, nxt, do_data=True, do_stop=True):
        """ helper function to connect to the next stage data/valid/ready.
            data/valid is passed *TO* nxt, and ready comes *IN* from nxt.
            use this when connecting stage-to-stage

            note: a "connect_from_prev" is completely unnecessary: it's
            just nxt.connect_to_next(self)
        """
        res = [nxt.valid_i.eq(self.valid_o),
               self.ready_i.eq(nxt.ready_o)]
        if self.maskwid:
            res.append(nxt.mask_i.eq(self.mask_o))
            if do_stop:
                res.append(nxt.stop_i.eq(self.stop_o))
        if do_data:
            res.append(nmoperator.eq(nxt.data_i, self.data_o))
        print ("connect to next", self, self.maskwid, nxt.data_i, do_data, do_stop)
        return res

    def _connect_out(self, nxt, direct=False, fn=None,
                     do_data=True, do_stop=True):
        """ internal helper function to connect stage to an output source.
            do not use to connect stage-to-stage!
        """
        ready_i = nxt.ready_i if direct else nxt.ready_i_test
        res = [nxt.valid_o.eq(self.valid_o),
               self.ready_i.eq(ready_i)]
        if self.maskwid:
            res.append(nxt.mask_o.eq(self.mask_o))
            if do_stop:
                res.append(nxt.stop_o.eq(self.stop_o))
        if not do_data:
            return res
        data_o = fn(nxt.data_o) if fn is not None else nxt.data_o
        return res + [nmoperator.eq(data_o, self.data_o)]

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.trigger.eq(self.ready_i_test & self.valid_o)
        return m

    def __iter__(self):
        yield self.ready_i
        yield self.valid_o
        if self.maskwid:
            yield self.mask_o
            yield self.stop_o
        if hasattr(self.data_o, "ports"):
            yield from self.data_o.ports()
        elif isinstance(self.data_o, Sequence):
            yield from self.data_o
        else:
            yield self.data_o

    def ports(self):
        return list(self)

