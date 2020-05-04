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
        assert self.width % 2 == 0  # TODO handle odd widths
        pairs = []
        for i in range(0, self.width, 2):
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
            pairs.append(pair_cnt)
        return pairs

    def combine_pairs(self, m, iteration, pairs):
        comb = m.d.comb
        length = len(pairs)
        assert length % 2 == 0  # TODO handle non powers of 2
        ret = []
        for i in range(0, length, 2):
            left = pairs[i+1]
            right = pairs[i]
            width = left.width + 1
            print(left)
            print(f"pair({i}, {i+1}) - cnt_{iteration}_{i}")
            new_pair = Signal(left.width + 1, name="cnt_%d_%d" %
                              (iteration, i))
            with m.If(left[-1] == 1):
                with m.If(right[-1] == 1):
                    comb += new_pair.eq(Cat(Repl(0, width-1), 1))
                with m.Else():
                    comb += new_pair.eq(Cat(right[0:-1], 0b01))
            with m.Else():
                comb += new_pair.eq(Cat(left, 0))

            ret.append(new_pair)
        return ret

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        pairs = self.generate_pairs(m)
        i = 2
        while len(pairs) > 1:
            pairs = self.combine_pairs(m, i, pairs)
            i += 1

        comb += self.lz.eq(pairs[0])

        return m

        
