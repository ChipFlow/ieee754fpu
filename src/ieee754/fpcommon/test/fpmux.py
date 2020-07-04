""" key strategic example showing how to do multi-input fan-in into a
    multi-stage pipeline, then multi-output fanout.

    the multiplex ID from the fan-in is passed in to the pipeline, preserved,
    and used as a routing ID on the fanout.
"""

import os
from random import randint
from nmigen.compat.sim import run_simulation
from nmigen.cli import verilog, rtlil


class MuxInOut:
    def __init__(self, dut, width, fpkls, fpop, vals, single_op, opcode,
                       cancel=False, feedback_width=None):
        self.cancel = cancel # allow (test) cancellation
        self.dut = dut
        self.fpkls = fpkls
        self.fpop = fpop
        self.single_op = single_op
        self.opcode = opcode
        self.di = {}
        self.do = {}
        self.sent = {}
        self.tlen = len(vals) // dut.num_rows
        self.width = width
        if feedback_width is None:
            feedback_width = dut.num_rows
        self.feedback_width = feedback_width
        self.out_offs = dut.num_rows - feedback_width
        for muxid in range(feedback_width):
            muxid_in = muxid
            muxid_out = muxid
            self.di[muxid_in] = {}
            self.do[muxid_out] = {}
            self.sent[muxid_in] = []

            for i in range(self.tlen):
                if self.single_op:
                    #print ("vals", vals)
                    op1 = vals.pop(0)
                    if isinstance(op1, tuple):
                        assert len(op1) == 1
                        op1 = op1[0]
                    res = self.fpop(self.fpkls(op1))
                    self.di[muxid_in][i] = (op1, )
                else:
                    (op1, op2, ) = vals.pop(0)
                    #print ("test", hex(op1), hex(op2))
                    res = self.fpop(self.fpkls(op1), self.fpkls(op2))
                    self.di[muxid_in][i] = (op1, op2)
                if hasattr(res, "bits"):
                    self.do[muxid_out][i] = res.bits
                else:
                    self.do[muxid_out][i] = res # for FP to INT

    def send(self, muxid):
        rs = self.dut.p[muxid]
        for i in range(self.tlen):
            if self.single_op:
                op1, = self.di[muxid][i]
            else:
                op1, op2 = self.di[muxid][i]
            yield rs.valid_i.eq(1)
            yield rs.data_i.a.eq(op1)
            if self.opcode is not None:
                yield rs.data_i.ctx.op.eq(self.opcode)
            if not self.single_op:
                yield rs.data_i.b.eq(op2)
            yield rs.data_i.muxid.eq(muxid)
            if hasattr(rs, "mask_i"):
                yield rs.mask_i.eq(1) # TEMPORARY HACK
            yield
            o_p_ready = yield rs.ready_o
            while not o_p_ready:
                yield
                o_p_ready = yield rs.ready_o

            if self.single_op:
                fop1 = self.fpkls(op1)
                res = self.fpop(fop1)
                if hasattr(res, "bits"):
                    r = res.bits
                else:
                    r = res
                print("send", muxid, i, hex(op1), hex(r),
                              fop1, res)
            else:
                fop1 = self.fpkls(op1)
                fop2 = self.fpkls(op2)
                res = self.fpop(fop1, fop2)
                print("send", muxid, i, hex(op1), hex(op2), hex(res.bits),
                              fop1, fop2, res)

            self.sent[muxid].append(i)

            yield rs.valid_i.eq(0)
            if hasattr(rs, "mask_i"):
                yield rs.mask_i.eq(0) # TEMPORARY HACK
            # wait until it's received
            while i in self.sent[muxid]:
                yield

            # wait random period of time before queueing another value
            for i in range(randint(0, 3)):
                yield

        yield rs.valid_i.eq(0)
        yield

        print("send ended", muxid)

        ## wait random period of time before queueing another value
        #for i in range(randint(0, 3)):
        #    yield

        #send_range = randint(0, 3)
        #if send_range == 0:
        #    send = True
        #else:
        #    send = randint(0, send_range) != 0

    def rcv(self, muxid):
        rs = self.dut.p[muxid]
        while True:

            # check cancellation
            cancel = self.cancel and (randint(0, 2) == 0)
            if hasattr(rs, "mask_i") and len(self.sent[muxid]) > 0 and cancel:
                todel = self.sent[muxid].pop()
                print ("to delete", muxid, self.sent[muxid], todel)
                if todel in self.do[muxid]:
                    del self.do[muxid][todel]
                    yield rs.stop_i.eq(1)
                print ("left", muxid, self.do[muxid])
                if len(self.do[muxid]) == 0:
                    break

            #stall_range = randint(0, 3)
            #for j in range(randint(1,10)):
            #    stall = randint(0, stall_range) != 0
            #    yield self.dut.n[0].ready_i.eq(stall)
            #    yield
            n = self.dut.n[muxid]
            yield n.ready_i.eq(1)
            yield
            if hasattr(rs, "mask_i"):
                yield rs.stop_i.eq(0) # resets cancel mask

            o_n_valid = yield n.valid_o
            i_n_ready = yield n.ready_i
            if not o_n_valid or not i_n_ready:
                continue

            out_muxid = yield n.data_o.muxid
            out_z = yield n.data_o.z

            if not self.sent[muxid]:
                print ("cancelled/recv", muxid, hex(out_z))
                continue

            out_i = self.sent[muxid].pop()

            print("recv", out_muxid, hex(out_z), "expected",
                  hex(self.do[muxid][out_i]))

            # see if this output has occurred already, delete it if it has
            assert muxid == out_muxid, "out_muxid %d not correct %d" % \
                                       (out_muxid, muxid)

            assert self.do[muxid][out_i] == out_z

            print ("senddel", muxid, out_i, self.sent[muxid])
            del self.do[muxid][out_i]

            # check if there's any more outputs
            if len(self.do[muxid]) == 0:
                break

        print("recv ended", muxid)


def create_random(num_rows, width, single_op=False, n_vals=10):
    vals = []
    for muxid in range(num_rows):
        for i in range(n_vals):
            if single_op:
                op1 = randint(0, (1 << width)-1)
                #op1 = 0x40900000
                #op1 = 0x94607b66
                #op1 = 0x889cd8c
                #op1 = 0xe98646d7
                #op1 = 0x3340f2a7
                #op1 = 0xfff13f05
                #op1 = 0x453eb000
                #op1 = 0x3a05de50
                #op1 = 0xc27ff989
                #op1 = 0x41689000
                #op1 = 0xbbc0edec
                #op1 = 0x2EDBE6FF
                #op1 = 0x358637BD
                #op1 = 0x3340f2a7
                #op1 = 0x33D6BF95
                #op1 = 0x9885020648d8c0e8
                #op1 = 0xc26b
                #op1 = 3

                #op1 = 0x3a66
                #op1 = 0x5299
                #op1 = 0xe0eb
                #op1 = 0x3954
                #op1 = 0x4dea
                #op1 = 0x65eb

                #op1 = 0x1841

                # FSQRT
                #op1 = 0x3449f9a9
                #op1 = 0x1ba94baa

                #if i % 2:
                #    op1 = 0x0001
                #else:
                #    op1 = 0x3C00

                # FRSQRT
                #op1 = 0x3686
                #op1 = 0x4400
                #op1 = 0x4800
                #op1 = 0x48f0
                #op1 = 0x429
                #op1 = 0x2631
                #op1 = 0x3001
                #op1 = 0x3f2ad8eb

                # f2int
                #op1 = 0x4dc0
                #op1 = 0x3b81
                #op1 = 0xfcb6
                #op1 = 0x4f8d77b3

                # f2int signed
                #op1 = 0xc913
                #op1 = 0x7b97
                #op1 = 0xaae2
                #op1 = 0x7fca

                # FCLASS
                #op1 = 0x87d1
                #op1 = 0x75e
                #op1 = 0x7f8c
                #op1 = 0x7c57
                #op1 = 0xfea8
                #op1 = 0xfd57

                # f2int unsigned (fp64 to ui16)
                #op1 = 0x40e6f5bc4d88b0cc

                # f2int signed (fp64 to i16)
                #op1 = 0xff292cf09f159ddb
                #op1 = 0x5880e09f7cb716a1

                # f2int signed (fp64 to i32)
                #op1 = 0x5beb66ffc69a9a64
                #op1 = 0xd4cdd178a1f2cdec

                vals.append((op1,))
            else:
                op1 = randint(0, (1 << width)-1)
                op2 = randint(0, (1 << width)-1)
                # op1 = 0x3F800000  # 1.0f32
                # op2 = 0x40000000  # 2.0f32

                #op2 = 0x4000
                #op1 = 0x3c50
                #op2 = 0x3e00
                #op2 = 0xb371
                #op1 = 0x4400
                #op1 = 0x656c
                #op1 = 0x738c

                vals.append((op1, op2,))
    return vals


def repeat(num_rows, vals):
    """ bit of a hack: repeats the last value to create a list
        that will be accepted by the muxer, all mux lists to be
        of equal length
    """
    vals = list(vals)
    n_to_repeat = len(vals) % num_rows
    #print ("repeat", vals)
    return vals + [vals[-1]] * n_to_repeat


def pipe_cornercases_repeat(dut, name, mod, fmod, width, fn, cc, fpfn, count,
                            single_op=False, opcode=None):
    for i, fixed_num in enumerate(cc(mod)):
        vals = fn(mod, fixed_num, count, width, single_op)
        vals = repeat(dut.num_rows, vals)
        #print ("repeat", i, fn, single_op, list(vals))
        fmt = "test_pipe_fp%d_%s_cornercases_%d"
        runfp(dut, width, fmt % (width, name, i),
              fmod, fpfn, vals=vals, single_op=single_op, opcode=opcode)


def runfp(dut, width, name, fpkls, fpop, single_op=False, n_vals=10,
          vals=None, opcode=None, cancel=False, feedback_width=None):
    if not os.path.exists("sim_out"):
        os.makedirs("sim_out")
    vl = rtlil.convert(dut, ports=dut.ports())
    with open("sim_out/%s.il" % name, "w") as f:
        f.write(vl)

    if vals is None:
        vals = create_random(dut.num_rows, width, single_op, n_vals)

    test = MuxInOut(dut, width, fpkls, fpop, vals, single_op, opcode=opcode)
    fns = []
    n_rows = dut.num_rows
    if feedback_width is not None:
        n_rows = feedback_width
    for i in range(n_rows):
        fns.append(test.rcv(i))
        fns.append(test.send(i))
    run_simulation(dut, {"sync": fns}, vcd_name="sim_out/%s.vcd" % name)
