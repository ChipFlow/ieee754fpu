""" nmigen implementation of buffered pipeline stage, based on zipcpu:
    https://zipcpu.com/blog/2017/08/14/strategies-for-pipelining.html

    this module requires quite a bit of thought to understand how it works
    (and why it is needed in the first place).  reading the above is
    *strongly* recommended.

    unlike john dawson's IEEE754 FPU STB/ACK signalling, which requires
    the STB / ACK signals to raise and lower (on separate clocks) before
    data may proceeed (thus only allowing one piece of data to proceed
    on *ALTERNATE* cycles), the signalling here is a true pipeline
    where data will flow on *every* clock when the conditions are right.

    input acceptance conditions are when:
        * incoming previous-stage strobe (i_p_stb) is HIGH
        * outgoing previous-stage busy   (o_p_busy) is LOW

    output transmission conditions are when:
        * outgoing next-stage strobe (o_n_stb) is HIGH
        * outgoing next-stage busy   (i_n_busy) is LOW

    the tricky bit is when the input has valid data and the output is not
    ready to accept it.  if it wasn't for the clock synchronisation, it
    would be possible to tell the input "hey don't send that data, we're
    not ready".  unfortunately, it's not possible to "change the past":
    the previous stage *has no choice* but to pass on its data.

    therefore, the incoming data *must* be accepted - and stored.
    on the same clock, it's possible to tell the input that it must
    not send any more data.  this is the "stall" condition.

    we now effectively have *two* possible pieces of data to "choose" from:
    the buffered data, and the incoming data.  the decision as to which
    to process and output is based on whether we are in "stall" or not.
    i.e. when the next stage is no longer busy, the output comes from
    the buffer if a stall had previously occurred, otherwise it comes
    direct from processing the input.

    it's quite a complex state machine!
"""

from nmigen import Signal, Cat, Const, Mux, Module
from nmigen.cli import verilog, rtlil

class BufPipe:
    """ buffered pipeline stage

        stage-1   i_p_stb  >>in   stage   o_n_stb  out>>   stage+1
        stage-1   o_p_busy <<out  stage   i_n_busy <<in    stage+1
        stage-1   i_data   >>in   stage   o_data   out>>   stage+1
                              |             |
                              +------->  process
                              |             |
                              +-- r_data ---+
    """
    def __init__(self):
        # input
        #self.i_p_rst = Signal()    # >>in - comes in from PREVIOUS stage
        self.i_p_stb = Signal()    # >>in - comes in from PREVIOUS stage
        self.i_n_busy = Signal()   # in<< - comes in from the NEXT stage
        self.i_data = Signal(16) # >>in - comes in from the PREVIOUS stage
        #self.i_rst = Signal()

        # buffered
        self.r_data = Signal(16)

        # output
        self.o_n_stb = Signal()    # out>> - goes out to the NEXT stage
        self.o_p_busy = Signal()   # <<out - goes out to the PREVIOUS stage
        self.o_data = Signal(16) # out>> - goes out to the NEXT stage

    def pre_process(self, d_in):
        return d_in | 0xf0000

    def process(self, d_in):
        return d_in + 1

    def elaborate(self, platform):
        m = Module()

        # establish some combinatorial temporaries
        o_p_busyn = Signal(reset_less=True)
        o_n_stbn = Signal(reset_less=True)
        i_n_busyn = Signal(reset_less=True)
        i_p_stb_o_p_busyn = Signal(reset_less=True)
        m.d.comb += [i_n_busyn.eq(~self.i_n_busy),
                     o_n_stbn.eq(~self.o_n_stb),
                     o_p_busyn.eq(~self.o_p_busy),
                     i_p_stb_o_p_busyn.eq(self.i_p_stb & o_p_busyn),
        ]

        # store result of processing in combinatorial temporary
        result = Signal(16)
        with m.If(self.i_p_stb): # input is valid: process it
            m.d.comb += result.eq(self.process(self.i_data))
        with m.If(o_p_busyn): # not stalled
            m.d.sync += self.r_data.eq(result)

        #with m.If(self.i_p_rst): # reset
        #    m.d.sync += self.o_n_stb.eq(0)
        #    m.d.sync += self.o_p_busy.eq(0)
        with m.If(i_n_busyn): # next stage is not busy
            with m.If(o_p_busyn): # not stalled
                # nothing in buffer: send input direct to output
                m.d.sync += [self.o_n_stb.eq(self.i_p_stb),
                             self.o_data.eq(result),
                            ]
            with m.Else(): # o_p_busy is true, and something is in our buffer.
                # Flush the [already processed] buffer to the output port.
                m.d.sync += [self.o_n_stb.eq(1),
                             self.o_data.eq(self.r_data),
                             # clear stall condition, declare register empty.
                             self.o_p_busy.eq(0),
                            ]
                # ignore input, since o_p_busy is also true.

        # (i_n_busy) is true here: next stage is busy
        with m.Elif(o_n_stbn): # next stage being told "not busy"
            m.d.sync += [self.o_n_stb.eq(self.i_p_stb),
                         self.o_p_busy.eq(0), # Keep the buffer empty
                         # set the output data (from comb result)
                         self.o_data.eq(result),
                        ]
        # (i_n_busy) and (o_n_stb) both true:
        with m.Elif(i_p_stb_o_p_busyn):
            # If next stage *is* busy, and not stalled yet, accept input
            m.d.sync += self.o_p_busy.eq(self.i_p_stb & self.o_n_stb)

        with m.If(o_p_busyn): # not stalled
            # turns out that from all of the above conditions, just
            # always put result into buffer if not busy
            m.d.sync += self.r_data.eq(result)

        return m

    def ports(self):
        return [self.i_p_stb, self.i_n_busy, self.i_data,
                self.r_data,
                self.o_n_stb, self.o_p_busy, self.o_data
               ]


if __name__ == '__main__':
    dut = BufPipe()
    vl = rtlil.convert(dut, ports=dut.ports())
    with open("test_bufpipe.il", "w") as f:
        f.write(vl)

