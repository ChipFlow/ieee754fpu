""" Pipeline and BufferedPipeline examples
"""

from singlepipe import (PrevControl, NextControl, ControlBase,
                        StageCls, Stage, StageChain,
                        BufferedPipeline, UnbufferedPipeline, eq)

from nmigen import Signal, Cat, Const, Mux, Module
from nmigen.cli import verilog, rtlil
from nmigen.hdl.rec import Record, Layout

from abc import ABCMeta, abstractmethod
from collections.abc import Sequence


class ExampleAddStage(StageCls):
    """ an example of how to use the buffered pipeline, as a class instance
    """

    def ispec(self):
        """ returns a tuple of input signals which will be the incoming data
        """
        return (Signal(16), Signal(16))

    def ospec(self):
        """ returns an output signal which will happen to contain the sum
            of the two inputs
        """
        return Signal(16)

    def process(self, i):
        """ process the input data (sums the values in the tuple) and returns it
        """
        return i[0] + i[1]


class ExampleBufPipeAdd(BufferedPipeline):
    """ an example of how to use the buffered pipeline, using a class instance
    """

    def __init__(self):
        addstage = ExampleAddStage()
        BufferedPipeline.__init__(self, addstage)


class ExampleStage(Stage):
    """ an example of how to use the buffered pipeline, in a static class
        fashion
    """

    def ispec():
        return Signal(16, name="example_input_signal")

    def ospec():
        return Signal(16, name="example_output_signal")

    def process(i):
        """ process the input data and returns it (adds 1)
        """
        return i + 1


class ExampleStageCls(StageCls):
    """ an example of how to use the buffered pipeline, in a static class
        fashion
    """

    def ispec(self):
        return Signal(16, name="example_input_signal")

    def ospec(self):
        return Signal(16, name="example_output_signal")

    def process(self, i):
        """ process the input data and returns it (adds 1)
        """
        return i + 1


class ExampleBufPipe(BufferedPipeline):
    """ an example of how to use the buffered pipeline.
    """

    def __init__(self):
        BufferedPipeline.__init__(self, ExampleStage)


class ExamplePipeline(UnbufferedPipeline):
    """ an example of how to use the unbuffered pipeline.
    """

    def __init__(self):
        UnbufferedPipeline.__init__(self, ExampleStage)


if __name__ == '__main__':
    dut = ExampleBufPipe()
    vl = rtlil.convert(dut, ports=dut.ports())
    with open("test_bufpipe.il", "w") as f:
        f.write(vl)

    dut = ExamplePipeline()
    vl = rtlil.convert(dut, ports=dut.ports())
    with open("test_combpipe.il", "w") as f:
        f.write(vl)
