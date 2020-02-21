#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

from nmigen import Signal, Module, Elaboratable
from nmigen.back.pysim import Simulator, Delay
from nmigen.cli import rtlil

from ieee754.part.partsig import PartitionedSignal
from ieee754.part_mux.part_mux import PMux

from random import randint
import unittest
import itertools
import math

def first_zero(x):
    res = 0
    for i in range(16):
        if x & (1<<i):
            return res
        res += 1

def count_bits(x):
    res = 0
    for i in range(16):
        if x & (1<<i):
            res += 1
    return res


def perms(k):
    return map(''.join, itertools.product('01', repeat=k))


def create_ilang(dut, traces, test_name):
    vl = rtlil.convert(dut, ports=traces)
    with open("%s.il" % test_name, "w") as f:
        f.write(vl)


def create_simulator(module, traces, test_name):
    create_ilang(module, traces, test_name)
    return Simulator(module,
                     vcd_file=open(test_name + ".vcd", "w"),
                     gtkw_file=open(test_name + ".gtkw", "w"),
                     traces=traces)


# XXX this is for coriolis2 experimentation
class TestAddMod2(Elaboratable):
    def __init__(self, width, partpoints):
        self.partpoints = partpoints
        self.a = PartitionedSignal(partpoints, width)
        self.b = PartitionedSignal(partpoints, width)
        self.bsig = Signal(width)
        self.add_output = Signal(width)
        self.ls_output = Signal(width) # left shift
        self.ls_scal_output = Signal(width) # left shift
        self.sub_output = Signal(width)
        self.eq_output = Signal(len(partpoints)+1)
        self.gt_output = Signal(len(partpoints)+1)
        self.ge_output = Signal(len(partpoints)+1)
        self.ne_output = Signal(len(partpoints)+1)
        self.lt_output = Signal(len(partpoints)+1)
        self.le_output = Signal(len(partpoints)+1)
        self.mux_sel = Signal(len(partpoints)+1)
        self.mux_out = Signal(width)
        self.carry_in = Signal(len(partpoints)+1)
        self.add_carry_out = Signal(len(partpoints)+1)
        self.sub_carry_out = Signal(len(partpoints)+1)
        self.neg_output = Signal(width)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        sync = m.d.sync
        self.a.set_module(m)
        self.b.set_module(m)
        # compares
        sync += self.lt_output.eq(self.a < self.b)
        sync += self.ne_output.eq(self.a != self.b)
        sync += self.le_output.eq(self.a <= self.b)
        sync += self.gt_output.eq(self.a > self.b)
        sync += self.eq_output.eq(self.a == self.b)
        sync += self.ge_output.eq(self.a >= self.b)
        # add
        add_out, add_carry = self.a.add_op(self.a, self.b,
                                           self.carry_in)
        sync += self.add_output.eq(add_out)
        sync += self.add_carry_out.eq(add_carry)
        # sub
        sub_out, sub_carry = self.a.sub_op(self.a, self.b,
                                           self.carry_in)
        sync += self.sub_output.eq(sub_out)
        sync += self.sub_carry_out.eq(sub_carry)
        # neg
        sync += self.neg_output.eq(-self.a)
        # left shift
        sync += self.ls_output.eq(self.a << self.b)
        ppts = self.partpoints
        sync += self.mux_out.eq(PMux(m, ppts, self.mux_sel, self.a, self.b))
        # scalar left shift
        comb += self.bsig.eq(self.b.sig)
        sync += self.ls_scal_output.eq(self.a << self.bsig)

        return m


class TestAddMod(Elaboratable):
    def __init__(self, width, partpoints):
        self.partpoints = partpoints
        self.a = PartitionedSignal(partpoints, width)
        self.b = PartitionedSignal(partpoints, width)
        self.bsig = Signal(width)
        self.add_output = Signal(width)
        self.ls_output = Signal(width) # left shift
        self.ls_scal_output = Signal(width) # left shift
        self.sub_output = Signal(width)
        self.eq_output = Signal(len(partpoints)+1)
        self.gt_output = Signal(len(partpoints)+1)
        self.ge_output = Signal(len(partpoints)+1)
        self.ne_output = Signal(len(partpoints)+1)
        self.lt_output = Signal(len(partpoints)+1)
        self.le_output = Signal(len(partpoints)+1)
        self.mux_sel = Signal(len(partpoints)+1)
        self.mux_out = Signal(width)
        self.carry_in = Signal(len(partpoints)+1)
        self.add_carry_out = Signal(len(partpoints)+1)
        self.sub_carry_out = Signal(len(partpoints)+1)
        self.neg_output = Signal(width)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        sync = m.d.sync
        self.a.set_module(m)
        self.b.set_module(m)
        # compares
        comb += self.lt_output.eq(self.a < self.b)
        comb += self.ne_output.eq(self.a != self.b)
        comb += self.le_output.eq(self.a <= self.b)
        comb += self.gt_output.eq(self.a > self.b)
        comb += self.eq_output.eq(self.a == self.b)
        comb += self.ge_output.eq(self.a >= self.b)
        # add
        add_out, add_carry = self.a.add_op(self.a, self.b,
                                           self.carry_in)
        comb += self.add_output.eq(add_out)
        comb += self.add_carry_out.eq(add_carry)
        # sub
        sub_out, sub_carry = self.a.sub_op(self.a, self.b,
                                           self.carry_in)
        comb += self.sub_output.eq(sub_out)
        comb += self.sub_carry_out.eq(sub_carry)
        # neg
        comb += self.neg_output.eq(-self.a)
        # left shift
        comb += self.ls_output.eq(self.a << self.b)
        ppts = self.partpoints
        comb += self.mux_out.eq(PMux(m, ppts, self.mux_sel, self.a, self.b))
        # scalar left shift
        comb += self.bsig.eq(self.b.sig)
        comb += self.ls_scal_output.eq(self.a << self.bsig)

        return m


class TestPartitionPoints(unittest.TestCase):
    def test(self):
        width = 16
        part_mask = Signal(4)  # divide into 4-bits
        module = TestAddMod(width, part_mask)

        sim = create_simulator(module,
                               [part_mask,
                                module.a.sig,
                                module.b.sig,
                                module.add_output,
                                module.eq_output],
                               "part_sig_add")

        def async_process():

            def test_ls_scal_fn(carry_in, a, b, mask):
                # reduce range of b
                bits = count_bits(mask)
                newb = b & ((bits-1))
                print ("%x %x %x bits %d trunc %x" % \
                        (a, b, mask, bits, newb))
                b = newb
                # TODO: carry
                carry_in = 0
                lsb = mask & ~(mask-1) if carry_in else 0
                sum = ((a & mask) << b)
                result = mask & sum
                carry = (sum & mask) != sum
                carry = 0
                print("res", hex(a), hex(b), hex(sum), hex(mask), hex(result))
                return result, carry

            def test_ls_fn(carry_in, a, b, mask):
                # reduce range of b
                bits = count_bits(mask)
                fz = first_zero(mask)
                newb = b & ((bits-1)<<fz)
                print ("%x %x %x bits %d zero %d trunc %x" % \
                        (a, b, mask, bits, fz, newb))
                b = newb
                # TODO: carry
                carry_in = 0
                lsb = mask & ~(mask-1) if carry_in else 0
                b = (b & mask)
                b = b >>fz
                sum = ((a & mask) << b)
                result = mask & sum
                carry = (sum & mask) != sum
                carry = 0
                print("res", hex(a), hex(b), hex(sum), hex(mask), hex(result))
                return result, carry

            def test_add_fn(carry_in, a, b, mask):
                lsb = mask & ~(mask-1) if carry_in else 0
                sum = (a & mask) + (b & mask) + lsb
                result = mask & sum
                carry = (sum & mask) != sum
                print(a, b, sum, mask)
                return result, carry

            def test_sub_fn(carry_in, a, b, mask):
                lsb = mask & ~(mask-1) if carry_in else 0
                sum = (a & mask) + (~b & mask) + lsb
                result = mask & sum
                carry = (sum & mask) != sum
                return result, carry

            def test_neg_fn(carry_in, a, b, mask):
                return test_add_fn(0, a, ~0, mask)

            def test_op(msg_prefix, carry, test_fn, mod_attr, *mask_list):
                rand_data = []
                for i in range(100):
                    a, b = randint(0, 1 << 16), randint(0, 1 << 16)
                    rand_data.append((a, b))
                for a, b in [(0x0000, 0x0000),
                             (0x1234, 0x1234),
                             (0xABCD, 0xABCD),
                             (0xFFFF, 0x0000),
                             (0x0000, 0x0000),
                             (0xFFFF, 0xFFFF),
                             (0x0000, 0xFFFF)] + rand_data:
                    yield module.a.eq(a)
                    yield module.b.eq(b)
                    carry_sig = 0xf if carry else 0
                    yield module.carry_in.eq(carry_sig)
                    yield Delay(0.1e-6)
                    y = 0
                    carry_result = 0
                    for i, mask in enumerate(mask_list):
                        print ("i/mask", i, hex(mask))
                        res, c = test_fn(carry, a, b, mask)
                        y |= res
                        lsb = mask & ~(mask - 1)
                        bit_set = int(math.log2(lsb))
                        carry_result |= c << int(bit_set/4)
                    outval = (yield getattr(module, "%s_output" % mod_attr))
                    # TODO: get (and test) carry output as well
                    print(a, b, outval, carry)
                    msg = f"{msg_prefix}: 0x{a:X} {mod_attr} 0x{b:X}" + \
                        f" => 0x{y:X} != 0x{outval:X}"
                    self.assertEqual(y, outval, msg)
                    if hasattr(module, "%s_carry_out" % mod_attr):
                        c_outval = (yield getattr(module,
                                                  "%s_carry_out" % mod_attr))
                        msg = f"{msg_prefix}: 0x{a:X} {mod_attr} 0x{b:X}" + \
                            f" => 0x{carry_result:X} != 0x{c_outval:X}"
                        self.assertEqual(carry_result, c_outval, msg)

            for (test_fn, mod_attr) in (
                                        (test_ls_scal_fn, "ls_scal"),
                                        (test_ls_fn, "ls"),
                                        (test_add_fn, "add"),
                                        (test_sub_fn, "sub"),
                                        (test_neg_fn, "neg"),
                                        ):
                yield part_mask.eq(0)
                yield from test_op("16-bit", 1, test_fn, mod_attr, 0xFFFF)
                yield from test_op("16-bit", 0, test_fn, mod_attr, 0xFFFF)
                yield part_mask.eq(0b10)
                yield from test_op("8-bit", 0, test_fn, mod_attr,
                                   0xFF00, 0x00FF)
                yield from test_op("8-bit", 1, test_fn, mod_attr,
                                   0xFF00, 0x00FF)
                yield part_mask.eq(0b1111)
                yield from test_op("4-bit", 0, test_fn, mod_attr,
                                   0xF000, 0x0F00, 0x00F0, 0x000F)
                yield from test_op("4-bit", 1, test_fn, mod_attr,
                                   0xF000, 0x0F00, 0x00F0, 0x000F)

            def test_ne_fn(a, b, mask):
                return (a & mask) != (b & mask)

            def test_lt_fn(a, b, mask):
                return (a & mask) < (b & mask)

            def test_le_fn(a, b, mask):
                return (a & mask) <= (b & mask)

            def test_eq_fn(a, b, mask):
                return (a & mask) == (b & mask)

            def test_gt_fn(a, b, mask):
                return (a & mask) > (b & mask)

            def test_ge_fn(a, b, mask):
                return (a & mask) >= (b & mask)

            def test_binop(msg_prefix, test_fn, mod_attr, *maskbit_list):
                for a, b in [(0x0000, 0x0000),
                             (0x1234, 0x1234),
                             (0xABCD, 0xABCD),
                             (0xFFFF, 0x0000),
                             (0x0000, 0x0000),
                             (0xFFFF, 0xFFFF),
                             (0x0000, 0xFFFF),
                             (0xABCD, 0xABCE),
                             (0x8000, 0x0000),
                             (0xBEEF, 0xFEED)]:
                    yield module.a.eq(a)
                    yield module.b.eq(b)
                    yield Delay(0.1e-6)
                    # convert to mask_list
                    mask_list = []
                    for mb in maskbit_list:
                        v = 0
                        for i in range(4):
                            if mb & (1 << i):
                                v |= 0xf << (i*4)
                        mask_list.append(v)
                    y = 0
                    # do the partitioned tests
                    for i, mask in enumerate(mask_list):
                        if test_fn(a, b, mask):
                            # OR y with the lowest set bit in the mask
                            y |= maskbit_list[i]
                    # check the result
                    outval = (yield getattr(module, "%s_output" % mod_attr))
                    msg = f"{msg_prefix}: {mod_attr} 0x{a:X} == 0x{b:X}" + \
                        f" => 0x{y:X} != 0x{outval:X}, masklist %s"
                    print((msg % str(maskbit_list)).format(locals()))
                    self.assertEqual(y, outval, msg % str(maskbit_list))

            for (test_fn, mod_attr) in ((test_eq_fn, "eq"),
                                        (test_gt_fn, "gt"),
                                        (test_ge_fn, "ge"),
                                        (test_lt_fn, "lt"),
                                        (test_le_fn, "le"),
                                        (test_ne_fn, "ne"),
                                        ):
                yield part_mask.eq(0)
                yield from test_binop("16-bit", test_fn, mod_attr, 0b1111)
                yield part_mask.eq(0b10)
                yield from test_binop("8-bit", test_fn, mod_attr,
                                      0b1100, 0b0011)
                yield part_mask.eq(0b1111)
                yield from test_binop("4-bit", test_fn, mod_attr,
                                      0b1000, 0b0100, 0b0010, 0b0001)

            def test_muxop(msg_prefix, *maskbit_list):
                for a, b in [(0x0000, 0x0000),
                             (0x1234, 0x1234),
                             (0xABCD, 0xABCD),
                             (0xFFFF, 0x0000),
                             (0x0000, 0x0000),
                             (0xFFFF, 0xFFFF),
                             (0x0000, 0xFFFF)]:
                    # convert to mask_list
                    mask_list = []
                    for mb in maskbit_list:
                        v = 0
                        for i in range(4):
                            if mb & (1 << i):
                                v |= 0xf << (i*4)
                        mask_list.append(v)

                    # TODO: sel needs to go through permutations of mask_list
                    for p in perms(len(mask_list)):

                        sel = 0
                        selmask = 0
                        for i, v in enumerate(p):
                            if v == '1':
                                sel |= maskbit_list[i]
                                selmask |= mask_list[i]

                        yield module.a.eq(a)
                        yield module.b.eq(b)
                        yield module.mux_sel.eq(sel)
                        yield Delay(0.1e-6)
                        y = 0
                        # do the partitioned tests
                        for i, mask in enumerate(mask_list):
                            if (selmask & mask):
                                y |= (a & mask)
                            else:
                                y |= (b & mask)
                        # check the result
                        outval = (yield module.mux_out)
                        msg = f"{msg_prefix}: mux " + \
                            f"0x{sel:X} ? 0x{a:X} : 0x{b:X}" + \
                            f" => 0x{y:X} != 0x{outval:X}, masklist %s"
                        # print ((msg % str(maskbit_list)).format(locals()))
                        self.assertEqual(y, outval, msg % str(maskbit_list))

            yield part_mask.eq(0)
            yield from test_muxop("16-bit", 0b1111)
            yield part_mask.eq(0b10)
            yield from test_muxop("8-bit", 0b1100, 0b0011)
            yield part_mask.eq(0b1111)
            yield from test_muxop("4-bit", 0b1000, 0b0100, 0b0010, 0b0001)

        sim.add_process(async_process)
        sim.run()


if __name__ == '__main__':
    unittest.main()
