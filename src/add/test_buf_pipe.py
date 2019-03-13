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

from nmigen.compat.sim import run_simulation
from example_buf_pipe import BufPipe


def testbench(dut):
    #yield dut.i_p_rst.eq(1)
    yield dut.i_n_busy.eq(1)
    yield dut.o_p_busy.eq(1)
    yield
    yield
    #yield dut.i_p_rst.eq(0)
    yield dut.i_n_busy.eq(0)
    yield dut.i_data.eq(5)
    yield dut.i_p_stb.eq(1)
    yield
    yield dut.i_data.eq(7)
    yield
    yield dut.i_data.eq(2)
    yield
    yield dut.i_n_busy.eq(1)
    yield dut.i_data.eq(9)
    yield
    yield dut.i_p_stb.eq(0)
    yield dut.i_data.eq(12)
    yield
    yield dut.i_data.eq(32)
    yield dut.i_n_busy.eq(0)
    yield
    yield
    yield
    yield


if __name__ == '__main__':
    dut = BufPipe()
    run_simulation(dut, testbench(dut), vcd_name="test_bufpipe.vcd")

