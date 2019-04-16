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

# translated from https://github.com/freechipsproject/chisel3/blob/a4a29e29c3f1eed18f851dcf10bdc845571dfcb6/src/main/scala/chisel3/util/Decoupled.scala#L185   # noqa


class Queue:
    def __init__(self,
                 data_width: int,
                 entries: int,
                 *,
                 pipe: bool = False,
                 flow: bool = False):
        self.entries = entries
        self.__pipe = pipe
        self.__flow = flow
        self.enq_data = Signal(data_width)
        self.enq_ready = Signal(1)
        self.enq_valid = Signal(1)
        self.deq_data = Signal(data_width)
        self.deq_ready = Signal(1)
        self.deq_valid = Signal(1)
        self.count = Signal(bits_for(entries))
        self.__ram = Memory(data_width, entries if entries > 1 else 2)
        self.__ram_read = self.__ram.read_port(synchronous=False)
        self.__ram_write = self.__ram.write_port()
        ptr_width = bits_for(entries - 1) if entries > 1 else 0
        self.__enq_ptr = Signal(ptr_width, reset=0)
        self.__deq_ptr = Signal(ptr_width, reset=0)
        self.__maybe_full = Signal(1, reset=0)
        self.__ptr_match = self.__enq_ptr == self.__deq_ptr
        self.__empty = self.__ptr_match & ~self.__maybe_full
        self.__full = self.__ptr_match & self.__maybe_full
        self.__do_enq = Signal(1)
        self.__do_deq = Signal(1)
        self.__ptr_diff = self.__enq_ptr - self.__deq_ptr

    def elaborate(self, platform: Any) -> Module:
        m = Module()
        m.submodules.ram_read = self.__ram_read
        m.submodules.ram_write = self.__ram_write
        m.d.comb += self.__do_enq.eq(self.enq_ready & self.enq_valid)
        m.d.comb += self.__do_deq.eq(self.deq_ready & self.deq_valid)
        m.d.comb += self.__ram_write.addr.eq(self.__enq_ptr)
        m.d.comb += self.__ram_write.data.eq(self.enq_data)
        m.d.comb += self.__ram_write.en.eq(0)
        with m.If(self.__do_enq):
            m.d.comb += self.__ram_write.en.eq(1)
            with m.If(self.__enq_ptr == self.entries - 1):
                m.d.sync += self.__enq_ptr.eq(0)
            with m.Else():
                m.d.sync += self.__enq_ptr.eq(self.__enq_ptr + 1)
        with m.If(self.__do_deq):
            with m.If(self.__deq_ptr == self.entries - 1):
                m.d.sync += self.__deq_ptr.eq(0)
            with m.Else():
                m.d.sync += self.__deq_ptr.eq(self.__deq_ptr + 1)
        with m.If(self.__do_enq != self.__do_deq):
            m.d.sync += self.__maybe_full.eq(self.__do_enq)
        m.d.comb += self.deq_valid.eq(~self.__empty)
        m.d.comb += self.enq_ready.eq(~self.__full)
        m.d.comb += self.__ram_read.addr.eq(self.__deq_ptr)
        m.d.comb += self.deq_data.eq(self.__ram_read.data)
        if self.__flow:
            with m.If(self.enq_valid):
                m.d.comb += self.deq_valid.eq(1)
            with m.If(self.__empty):
                m.d.comb += self.deq_data.eq(self.enq_data)
                m.d.comb += self.__do_deq.eq(0)
                with m.If(self.deq_ready):
                    m.d.comb += self.__do_enq.eq(0)

        if self.__pipe:
            with m.If(self.deq_ready):
                m.d.comb += self.enq_ready.eq(1)

        if self.entries == 1 << len(self.count):  # is entries a power of 2
            m.d.comb += self.count.eq(
                Mux(self.__maybe_full & self.__ptr_match, self.entries, 0)
                | self.__ptr_diff)
        else:
            m.d.comb += self.count.eq(Mux(
                self.__ptr_match,
                Mux(self.__maybe_full, self.entries, 0),
                Mux(self.__deq_ptr > self.__enq_ptr,
                    self.entries + self.__ptr_diff,
                    self.__ptr_diff)))

        return m


if __name__ == "__main__":
    reg_stage = Queue(1, 1, pipe=True)
    break_ready_chain_stage = Queue(1, 1, flow=True)
    m = Module()
    ports = []

    def queue_ports(queue: Queue, name_prefix: str) -> List[Signal]:
        retval = []
        for name in ["count",
                     "deq_data",
                     "deq_valid",
                     "enq_ready"]:
            port = getattr(queue, name)
            signal = Signal(port.shape(), name=name_prefix+name)
            m.d.comb += signal.eq(port)
            retval.append(signal)
        for name in ["deq_ready",
                     "enq_data",
                     "enq_valid"]:
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
