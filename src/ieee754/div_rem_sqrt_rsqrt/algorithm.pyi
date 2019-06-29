# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

from typing import Tuple


def div_rem(dividend: int,
            divisor: int,
            bit_width: int,
            signed: int) -> Tuple[int, int]:
    ...


class UnsignedDivRem:
    remainder: int
    divisor: int
    bit_width: int
    log2_radix: int
    quotient: int
    current_shift: int

    def __init__(self,
                 dividend: int,
                 divisor: int,
                 bit_width: int,
                 log2_radix: int = 3):
        ...

    def calculate_stage(self) -> bool:
        ...

    def calculate(self) -> 'UnsignedDivRem':
        ...
