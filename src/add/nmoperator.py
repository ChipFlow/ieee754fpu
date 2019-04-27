""" nmigen operator functions / utils

    eq:
    --

    a strategically very important function that is identical in function
    to nmigen's Signal.eq function, except it may take objects, or a list
    of objects, or a tuple of objects, and where objects may also be
    Records.
"""

from nmigen import Signal, Cat, Const, Mux, Module, Value, Elaboratable
from nmigen.cli import verilog, rtlil
from nmigen.lib.fifo import SyncFIFO, SyncFIFOBuffered
from nmigen.hdl.ast import ArrayProxy
from nmigen.hdl.rec import Record, Layout

from abc import ABCMeta, abstractmethod
from collections.abc import Sequence, Iterable
from collections import OrderedDict
from queue import Queue
import inspect


class Visitor2:
    """ a helper class for iterating twin-argument compound data structures.

        Record is a special (unusual, recursive) case, where the input may be
        specified as a dictionary (which may contain further dictionaries,
        recursively), where the field names of the dictionary must match
        the Record's field spec.  Alternatively, an object with the same
        member names as the Record may be assigned: it does not have to
        *be* a Record.

        ArrayProxy is also special-cased, it's a bit messy: whilst ArrayProxy
        has an eq function, the object being assigned to it (e.g. a python
        object) might not.  despite the *input* having an eq function,
        that doesn't help us, because it's the *ArrayProxy* that's being
        assigned to.  so.... we cheat.  use the ports() function of the
        python object, enumerate them, find out the list of Signals that way,
        and assign them.
    """
    def iterator2(self, o, i):
        if isinstance(o, dict):
            yield from self.dict_iter2(o, i)

        if not isinstance(o, Sequence):
            o, i = [o], [i]
        for (ao, ai) in zip(o, i):
            #print ("visit", fn, ao, ai)
            if isinstance(ao, Record):
                yield from self.record_iter2(ao, ai)
            elif isinstance(ao, ArrayProxy) and not isinstance(ai, Value):
                yield from self.arrayproxy_iter2(ao, ai)
            else:
                yield (ao, ai)

    def dict_iter2(self, o, i):
        for (k, v) in o.items():
            print ("d-iter", v, i[k])
            yield (v, i[k])
        return res

    def _not_quite_working_with_all_unit_tests_record_iter2(self, ao, ai):
        print ("record_iter2", ao, ai, type(ao), type(ai))
        if isinstance(ai, Value):
            if isinstance(ao, Sequence):
                ao, ai = [ao], [ai]
            for o, i in zip(ao, ai):
                yield (o, i)
            return
        for idx, (field_name, field_shape, _) in enumerate(ao.layout):
            if isinstance(field_shape, Layout):
                val = ai.fields
            else:
                val = ai
            if hasattr(val, field_name): # check for attribute
                val = getattr(val, field_name)
            else:
                val = val[field_name] # dictionary-style specification
            yield from self.iterator2(ao.fields[field_name], val)

    def record_iter2(self, ao, ai):
        for idx, (field_name, field_shape, _) in enumerate(ao.layout):
            if isinstance(field_shape, Layout):
                val = ai.fields
            else:
                val = ai
            if hasattr(val, field_name): # check for attribute
                val = getattr(val, field_name)
            else:
                val = val[field_name] # dictionary-style specification
            yield from self.iterator2(ao.fields[field_name], val)

    def arrayproxy_iter2(self, ao, ai):
        for p in ai.ports():
            op = getattr(ao, p.name)
            print ("arrayproxy - p", p, p.name)
            yield from self.iterator2(op, p)


class Visitor:
    """ a helper class for iterating single-argument compound data structures.
        similar to Visitor2.
    """
    def iterate(self, i):
        """ iterate a compound structure recursively using yield
        """
        if not isinstance(i, Sequence):
            i = [i]
        for ai in i:
            #print ("iterate", ai)
            if isinstance(ai, Record):
                #print ("record", list(ai.layout))
                yield from self.record_iter(ai)
            elif isinstance(ai, ArrayProxy) and not isinstance(ai, Value):
                yield from self.array_iter(ai)
            else:
                yield ai

    def record_iter(self, ai):
        for idx, (field_name, field_shape, _) in enumerate(ai.layout):
            if isinstance(field_shape, Layout):
                val = ai.fields
            else:
                val = ai
            if hasattr(val, field_name): # check for attribute
                val = getattr(val, field_name)
            else:
                val = val[field_name] # dictionary-style specification
            #print ("recidx", idx, field_name, field_shape, val)
            yield from self.iterate(val)

    def array_iter(self, ai):
        for p in ai.ports():
            yield from self.iterate(p)


def eq(o, i):
    """ makes signals equal: a helper routine which identifies if it is being
        passed a list (or tuple) of objects, or signals, or Records, and calls
        the objects' eq function.
    """
    res = []
    for (ao, ai) in Visitor2().iterator2(o, i):
        rres = ao.eq(ai)
        if not isinstance(rres, Sequence):
            rres = [rres]
        res += rres
    return res


def shape(i):
    #print ("shape", i)
    r = 0
    for part in list(i):
        #print ("shape?", part)
        s, _ = part.shape()
        r += s
    return r, False


def cat(i):
    """ flattens a compound structure recursively using Cat
    """
    from nmigen.tools import flatten
    #res = list(flatten(i)) # works (as of nmigen commit f22106e5) HOWEVER...
    res = list(Visitor().iterate(i)) # needed because input may be a sequence
    return Cat(*res)


