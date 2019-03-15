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
        * incoming previous-stage strobe (i.p_valid) is HIGH
        * outgoing previous-stage busy   (o.p_busy) is LOW

    output transmission conditions are when:
        * outgoing next-stage strobe (o.n_valid) is HIGH
        * outgoing next-stage busy   (i.n_busy) is LOW

    the tricky bit is when the input has valid data and the output is not
    ready to accept it.  if it wasn't for the clock synchronisation, it
    would be possible to tell the input "hey don't send that data, we're
    not ready".  unfortunately, it's not possible to "change the past":
    the previous stage *has no choice* but to pass on its data.

    therefore, the incoming data *must* be accepted - and stored: that
    is the responsibility / contract that this stage *must* accept.
    on the same clock, it's possible to tell the input that it must
    not send any more data.  this is the "stall" condition.

    we now effectively have *two* possible pieces of data to "choose" from:
    the buffered data, and the incoming data.  the decision as to which
    to process and output is based on whether we are in "stall" or not.
    i.e. when the next stage is no longer busy, the output comes from
    the buffer if a stall had previously occurred, otherwise it comes
    direct from processing the input.

    this allows us to respect a synchronous "travelling STB" with what
    dan calls a "buffered handshake".

    it's quite a complex state machine!
"""

from nmigen import Signal, Cat, Const, Mux, Module
from nmigen.cli import verilog, rtlil


class ExampleStage:
    """ an example of how to use the buffered pipeline.  actual names of
        variables (i_data, r_data, o_data, result) below do not matter:
        the functions however do.

        input data i_data is read (only), is processed and goes into an
        intermediate result store [process()].  this is updated combinatorially.

        in a non-stall condition, the intermediate result will go into the
        output (update_output).  however if ever there is a stall, it goes
        into r_data instead [update_buffer()].

        when the non-stall condition is released, r_data is the first
        to be transferred to the output [flush_buffer()], and the stall
        condition cleared.

        on the next cycle (as long as stall is not raised again) the
        input may begin to be processed and transferred directly to output.
    """

    def __init__(self):
        """ i_data can be a DIFFERENT type from everything else
            o_data, r_data and result must be of the same type
        """
        self.i_data = Signal(16)
        self.r_data = Signal(16)
        self.o_data = Signal(16)
        self.result = Signal(16)

    def process(self):
        """ process the input data and store it in result.
            (not needed to be known: result is combinatorial)
        """
        return self.result.eq(self.i_data + 1)

    def update_buffer(self):
        """ copies the result into the intermediate register r_data
        """
        return self.r_data.eq(self.result)

    def update_output(self):
        """ copies the (combinatorial) result into the output
        """
        return self.o_data.eq(self.result)

    def flush_buffer(self):
        """ copies the *intermediate* register r_data into the output
        """
        return self.o_data.eq(self.r_data)

    def ports(self):
        return [self.i_data, self.o_data]

class IOAckIn:

    def __init__(self):
        self.p_valid = Signal()  # >>in - comes in from PREVIOUS stage
        self.n_busy = Signal() # in<< - comes in from the NEXT stage


class IOAckOut:

    def __init__(self):
        self.n_valid = Signal()  # out>> - goes out to the NEXT stage
        self.p_busy = Signal() # <<out - goes out to the PREVIOUS stage


class BufferedPipeline:
    """ buffered pipeline stage

        stage-1   i.p_valid  >>in   stage   o.n_valid  out>>   stage+1
        stage-1   o.p_busy <<out  stage   i.n_busy <<in    stage+1
        stage-1   i_data   >>in   stage   o_data   out>>   stage+1
                              |             |
                              +------->  process
                              |             |
                              +-- r_data ---+
    """
    def __init__(self):
        # input: strobe comes in from previous stage, busy comes in from next
        self.i = IOAckIn()
        #self.i.p_valid = Signal()    # >>in - comes in from PREVIOUS stage
        #self.i.n_busy = Signal()   # in<< - comes in from the NEXT stage

        # output: strobe goes out to next stage, busy comes in from previous
        self.o = IOAckOut()
        #self.o.n_valid = Signal()    # out>> - goes out to the NEXT stage
        #self.o.p_busy = Signal()   # <<out - goes out to the PREVIOUS stage

    def elaborate(self, platform):
        m = Module()

        # establish some combinatorial temporaries
        o_p_busyn = Signal(reset_less=True)
        o_n_validn = Signal(reset_less=True)
        i_n_busyn = Signal(reset_less=True)
        i_p_valid_o_p_busyn = Signal(reset_less=True)
        m.d.comb += [i_n_busyn.eq(~self.i.n_busy),
                     o_n_validn.eq(~self.o.n_valid),
                     o_p_busyn.eq(~self.o.p_busy),
                     i_p_valid_o_p_busyn.eq(self.i.p_valid & o_p_busyn),
        ]

        # store result of processing in combinatorial temporary
        with m.If(self.i.p_valid): # input is valid: process it
            m.d.comb += self.stage.process()
        # if not in stall condition, update the temporary register
        with m.If(o_p_busyn): # not stalled
            m.d.sync += self.stage.update_buffer()

        #with m.If(self.i.p_rst): # reset
        #    m.d.sync += self.o.n_valid.eq(0)
        #    m.d.sync += self.o.p_busy.eq(0)
        with m.If(i_n_busyn): # next stage is not busy
            with m.If(o_p_busyn): # not stalled
                # nothing in buffer: send (processed) input direct to output
                m.d.sync += [self.o.n_valid.eq(self.i.p_valid),
                             self.stage.update_output(),
                            ]
            with m.Else(): # o.p_busy is true, and something is in our buffer.
                # Flush the [already processed] buffer to the output port.
                m.d.sync += [self.o.n_valid.eq(1),
                             self.stage.flush_buffer(),
                             # clear stall condition, declare register empty.
                             self.o.p_busy.eq(0),
                            ]
                # ignore input, since o.p_busy is also true.

        # (i.n_busy) is true here: next stage is busy
        with m.Elif(o_n_validn): # next stage being told "not busy"
            m.d.sync += [self.o.n_valid.eq(self.i.p_valid),
                         self.o.p_busy.eq(0), # Keep the buffer empty
                         # set the output data (from comb result)
                         self.stage.update_output(),
                        ]
        # (i.n_busy) and (o.n_valid) both true:
        with m.Elif(i_p_valid_o_p_busyn):
            # If next stage *is* busy, and not stalled yet, accept input
            m.d.sync += self.o.p_busy.eq(self.i.p_valid & self.o.n_valid)

        return m

    def ports(self):
        return [self.i.p_valid, self.i.n_busy,
                self.o.n_valid, self.o.p_busy,
               ]


class BufPipe(BufferedPipeline):

    def __init__(self):
        BufferedPipeline.__init__(self)
        self.stage = ExampleStage()

    def ports(self):
        return self.stage.ports() + BufferedPipeline.ports(self)


if __name__ == '__main__':
    dut = BufPipe()
    vl = rtlil.convert(dut, ports=dut.ports())
    with open("test_bufpipe.il", "w") as f:
        f.write(vl)
