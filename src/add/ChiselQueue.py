# Copyright (c) 2014 - 2019 The Regents of the University of
# California (Regents). All Rights Reserved.  Redistribution and use in
# source and binary forms, with or without modification, are permitted
# provided that the following conditions are met:
#    * Redistributions of source code must retain the above
#      copyright notice, this list of conditions and the following
#      two paragraphs of disclaimer.
#    * Redistributions in binary form must reproduce the above
#      copyright notice, this list of conditions and the following
#      two paragraphs of disclaimer in the documentation and/or other materials
#      provided with the distribution.
#    * Neither the name of the Regents nor the names of its contributors
#      may be used to endorse or promote products derived from this
#      software without specific prior written permission.
# IN NO EVENT SHALL REGENTS BE LIABLE TO ANY PARTY FOR DIRECT, INDIRECT,
# SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES, INCLUDING LOST PROFITS,
# ARISING OUT OF THE USE OF THIS SOFTWARE AND ITS DOCUMENTATION, EVEN IF
# REGENTS HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# REGENTS SPECIFICALLY DISCLAIMS ANY WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE. THE SOFTWARE AND ACCOMPANYING DOCUMENTATION, IF
# ANY, PROVIDED HEREUNDER IS PROVIDED "AS IS". REGENTS HAS NO OBLIGATION
# TO PROVIDE MAINTENANCE, SUPPORT, UPDATES, ENHANCEMENTS, OR
# MODIFICATIONS.

from nmigen import Module, Signal, Memory, Mux
from nmigen.tools import bits_for
from typing import Tuple, Any, List
from nmigen.cli import main
from nmigen.lib.fifo import FIFOInterface

# translated from https://github.com/freechipsproject/chisel3/blob/a4a29e29c3f1eed18f851dcf10bdc845571dfcb6/src/main/scala/chisel3/util/Decoupled.scala#L185   # noqa


class Queue(FIFOInterface):
    def __init__(self, width, depth, fwft=True, pipe=False):
        """ din  = enq_data, writable  = enq_ready, we = enq_valid
            dout = deq_data, re = deq_ready, readable = deq_valid
        """
        FIFOInterface.__init__(self, width, depth, fwft)
        self.pipe = pipe
        self.depth = depth
        self.count = Signal(bits_for(depth))

    def elaborate(self, platform):
        m = Module()

        ram = Memory(self.width, self.depth if self.depth > 1 else 2)
        ram_read = ram.read_port(synchronous=False)
        ram_write = ram.write_port()
        ptr_width = bits_for(self.depth - 1) if self.depth > 1 else 0

        enq_ptr = Signal(ptr_width)
        deq_ptr = Signal(ptr_width)
        maybe_full = Signal(reset_less=True)
        do_enq = Signal(reset_less=True)
        do_deq = Signal(reset_less=True)

        # temporaries
        ptr_diff = Signal(ptr_width)
        ptr_match = Signal(reset_less=True)
        empty = Signal(reset_less=True)
        full = Signal(reset_less=True)

        m.d.comb += [ptr_match.eq(enq_ptr == deq_ptr),
                     ptr_diff.eq(enq_ptr - deq_ptr),
                     empty.eq(ptr_match & ~maybe_full),
                     full.eq(ptr_match & maybe_full)]

        m.submodules.ram_read = ram_read
        m.submodules.ram_write = ram_write

        m.d.comb += [do_enq.eq(self.writable & self.we),
                     do_deq.eq(self.re & self.readable),
                     ram_write.addr.eq(enq_ptr),
                     ram_write.data.eq(self.din),
                     ram_write.en.eq(0)]

        with m.If(do_enq):
            m.d.comb += ram_write.en.eq(1)
            with m.If(enq_ptr == self.depth - 1):
                m.d.sync += enq_ptr.eq(0)
            with m.Else():
                m.d.sync += enq_ptr.eq(enq_ptr + 1)

        with m.If(do_deq):
            with m.If(deq_ptr == self.depth - 1):
                m.d.sync += deq_ptr.eq(0)
            with m.Else():
                m.d.sync += deq_ptr.eq(deq_ptr + 1)

        with m.If(do_enq != do_deq):
            m.d.sync += maybe_full.eq(do_enq)

        m.d.comb += [self.readable.eq(~empty),
                     self.writable.eq(~full),
                     ram_read.addr.eq(deq_ptr),
                     self.dout.eq(ram_read.data)]

        # first-word fall-through: same as "flow" parameter in Chisel3 Queue
        # basically instead of relying on the Memory characteristics (which
        # in FPGAs do not have write-through), then when the queue is empty
        # take the output directly from the input, i.e. *bypass* the SRAM.
        # this done combinatorially to give the exact same characteristics
        # as Memory "write-through"... without relying on a changing API
        if self.fwft:
            with m.If(self.we):
                m.d.comb += self.readable.eq(1)
            with m.If(empty):
                m.d.comb += self.dout.eq(self.din)
                m.d.comb += do_deq.eq(0)
                with m.If(self.re):
                    m.d.comb += do_enq.eq(0)

        if self.pipe:
            with m.If(self.re):
                m.d.comb += self.writable.eq(1)

        if self.depth == 1 << len(self.count):  # is depth a power of 2
            m.d.comb += self.count.eq(
                Mux(self.maybe_full & self.ptr_match, self.depth, 0)
                | self.ptr_diff)
        else:
            m.d.comb += self.count.eq(Mux(ptr_match,
                                          Mux(maybe_full, self.depth, 0),
                                          Mux(deq_ptr > enq_ptr,
                                              self.depth + ptr_diff,
                                              ptr_diff)))

        return m


if __name__ == "__main__":
    reg_stage = Queue(1, 1, pipe=True)
    break_ready_chain_stage = Queue(1, 1, pipe=True, fwft=True)
    m = Module()
    ports = []

    def queue_ports(queue, name_prefix):
        retval = []
        for name in ["count",
                     "dout",
                     "readable",
                     "writable"]:
            port = getattr(queue, name)
            signal = Signal(port.shape(), name=name_prefix+name)
            m.d.comb += signal.eq(port)
            retval.append(signal)
        for name in ["re",
                     "din",
                     "we"]:
            port = getattr(queue, name)
            signal = Signal(port.shape(), name=name_prefix+name)
            m.d.comb += port.eq(signal)
            retval.append(signal)
        return retval
    m.submodules.reg_stage = reg_stage
    ports += queue_ports(reg_stage, "reg_stage_")
    m.submodules.break_ready_chain_stage = break_ready_chain_stage
    ports += queue_ports(break_ready_chain_stage, "break_ready_chain_stage_")
    main(m, ports=ports)
