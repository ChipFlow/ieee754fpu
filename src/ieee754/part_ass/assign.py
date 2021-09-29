# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

"""
Copyright (C) 2021 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

dynamically-partitionable "assign" class, directly equivalent
to nmigen Assign

See:

* http://libre-riscv.org/3d_gpu/architecture/dynamic_simd/assign
* http://bugs.libre-riscv.org/show_bug.cgi?id=709

"""

from nmigen import Signal, Module, Elaboratable, Cat, Const, signed
from nmigen.back.pysim import Simulator, Settle
from nmutil.extend import ext

from ieee754.part_mul_add.partpoints import PartitionPoints
from ieee754.part.partsig import PartitionedSignal


modcount = 0 # global for now
def PAssign(m, arglist, mask):
    global modcount
    modcount += 1
    pc = PartitionedAssign(arglist, mask)
    setattr(m.submodules, "pass%d" % modcount, pc)
    return pc.output


def get_runlengths(pbit, size):
    res = []
    count = 1
    # identify where the 1s are, which indicates "start of a new partition"
    # we want a list of the lengths of all partitions
    for i in range(size):
        if pbit & (1<<i): # it's a 1: ends old partition, starts new
            res.append(count) # add partition
            count = 1 # start again
        else:
            count += 1
    # end reached, add whatever is left. could have done this by creating
    # "fake" extra bit on the partitions, but hey
    res.append(count)

    print ("get_runlengths", bin(pbit), size, res)

    return res


class PartitionedAssign(Elaboratable):
    def __init__(self, shape, assign, mask):
        """Create a ``PartitionedAssign`` operator
        """
        # work out the length (total of all PartitionedSignals)
        self.assign = assign
        if isinstance(mask, dict):
            mask = list(mask.values())
        self.mask = mask
        self.shape = shape
        self.output = PartitionedSignal(mask, self.shape, reset_less=True)
        self.partition_points = self.output.partpoints
        self.mwidth = len(self.partition_points)+1

    def get_chunk(self, y, numparts):
        x = self.assign
        keys = [0] + list(x.partpoints.keys()) + [len(x.sig)]
        # get current index and increment it (for next Assign chunk)
        upto = y[0]
        y[0] += numparts
        print ("getting", upto, numparts, keys, len(x.sig))
        # get the partition point as far as we are up to
        start = keys[upto]
        end = keys[upto+numparts]
        print ("start end", start, end, len(x.sig))
        return x.sig[start:end]

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        keys = list(self.partition_points.keys())
        print ("keys", keys, "values", self.partition_points.values())
        print ("mask", self.mask)
        outpartsize = len(self.output) // self.mwidth
        width, signed = self.output.shape()
        print ("width, signed", width, signed)

        with m.Switch(Cat(self.mask)):
            # for each partition possibility, create a Assign sequence
            for pbit in range(1<<len(keys)):
                # set up some indices pointing to where things have got
                # then when called below in the inner nested loop they give
                # the relevant sequential chunk
                output = []
                y = [0]
                # get a list of the length of each partition run
                runlengths = get_runlengths(pbit, len(keys))
                print ("pbit", bin(pbit), "runs", runlengths)
                for i in runlengths: # for each partition
                    thing = self.get_chunk(y, i) # sequential chunks
                    # now check the length: truncate, extend or leave-alone
                    outlen = i * outpartsize
                    tlen = len(thing)
                    thing = ext(thing, (tlen, signed), outlen)
                    output.append(thing)
                with m.Case(pbit):
                    # direct access to the underlying Signal
                    comb += self.output.sig.eq(Cat(*output))

        return m

    def ports(self):
        return [self.assign.sig, self.output.sig]


if __name__ == "__main__":
    from ieee754.part.test.test_partsig import create_simulator
    m = Module()
    mask = Signal(3)
    a = PartitionedSignal(mask, 32)
    m.submodules.ass = ass = PartitionedAssign(signed(48), a, mask)

    traces = ass.ports()
    sim = create_simulator(m, traces, "partass")

    def process():
        yield mask.eq(0b000)
        yield a.sig.eq(0xa12345c7)
        yield Settle()
        out = yield ass.output.sig
        print("out 000", bin(out), hex(out&0xfffffffffffffffffffffffff))
        yield mask.eq(0b010)
        yield Settle()
        out = yield ass.output.sig
        print("out 010", bin(out), hex(out&0xfffffffffffffffffffffffff))
        yield mask.eq(0b110)
        yield Settle()
        out = yield ass.output.sig
        print("out 110", bin(out), hex(out&0xfffffffffffffffffffffffff))
        yield mask.eq(0b111)
        yield Settle()
        out = yield ass.output.sig
        print("out 111", bin(out), hex(out&0xfffffffffffffffffffffffff))

    sim.add_process(process)
    with sim.write_vcd("partition_ass.vcd", "partition_ass.gtkw",
                        traces=traces):
        sim.run()
