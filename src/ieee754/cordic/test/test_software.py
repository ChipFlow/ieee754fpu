import math
import unittest
from python_sin_cos import run_cordic
import random

class SoftwareTestCase(unittest.TestCase):
    def test_extrabits(self):
        fracbits = 16
        extrabits = 18
        M = (1 << fracbits)
        print(M)
        for i in range(200000):
            f = random.uniform(-math.pi/2, math.pi/2)
            i = int(round(f * M))
            f = i/M
            print(f"int: {i}, float:{f}")
            i = i * (1<<extrabits)

            expected = int(round(math.sin(f) * M))

            sin, cos = run_cordic(i,
                                  fracbits=(fracbits+extrabits),
                                  log=False)
            sin = int(round(sin / (1<<extrabits)))

            print(f"expected: {expected}, actual: {sin}")
            self.assertEqual(expected, sin)


if __name__ == '__main__':
    unittest.main()
