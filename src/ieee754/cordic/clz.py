from nmigen import Module, Signal, Elaboratable, Cat, Repl
import math

class CLZ(Elaboratable):
    def __init__(self, width):
        self.width = width
        self.sig_in = Signal(width, reset_less=True)
        out_width = math.ceil(math.log2(width+1))
        self.lz = Signal(out_width)

    def generate_pairs(self, m):
        comb = m.d.comb
        pairs = []
        for i in range(0, self.width, 2):
            if i+1 >= self.width:
                pair = Signal(1, name="cnt_1_%d" % (i/2))
                comb += pair.eq(~self.sig_in[i])
                pairs.append((pair, 1))
            else:
                pair = Signal(2, name="pair%d" % i)
                comb += pair.eq(self.sig_in[i:i+2])

                pair_cnt = Signal(2, name="cnt_1_%d" % (i/2))
                with m.Switch(pair):
                    with m.Case(0):
                        comb += pair_cnt.eq(2)
                    with m.Case(1):
                        comb += pair_cnt.eq(1)
                    with m.Default():
                        comb += pair_cnt.eq(0)
                pairs.append((pair_cnt, 2))  # append pair, max_value
        return pairs

    def combine_pairs(self, m, iteration, pairs):
        comb = m.d.comb
        length = len(pairs)
        ret = []
        for i in range(0, length, 2):
            if i+1 >= length:
                right, mv = pairs[i]
                width = right.width
                new_pair = Signal(width, name="cnt_%d_%d" % (iteration, i))
                comb += new_pair.eq(Cat(right, 0))
                ret.append((new_pair, mv))
            else:
                left, lv = pairs[i+1]
                right, rv = pairs[i]
                width = right.width + 1
                new_pair = Signal(width, name="cnt_%d_%d" %
                                  (iteration, i))
                if rv == lv:
                    with m.If(left[-1] == 1):
                        with m.If(right[-1] == 1):
                            comb += new_pair.eq(Cat(Repl(0, width-1), 1))
                        with m.Else():
                            comb += new_pair.eq(Cat(right[0:-1], 0b01))
                    with m.Else():
                        comb += new_pair.eq(Cat(left, 0))
                else:
                    with m.If(left == lv):
                        comb += new_pair.eq(right + left)
                    with m.Else():
                        comb += new_pair.eq(left)
                        

                ret.append((new_pair, lv+rv))
        return ret

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        pairs = self.generate_pairs(m)
        i = 2
        while len(pairs) > 1:
            pairs = self.combine_pairs(m, i, pairs)
            i += 1

        comb += self.lz.eq(pairs[0][0])

        return m

        
