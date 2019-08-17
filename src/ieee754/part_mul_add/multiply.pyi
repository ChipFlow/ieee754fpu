# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information
"""Integer Multiplication."""

from typing import Any, NewType, Union, List, Dict, Iterable, Mapping, Optional
from typing_extensions import final

PartitionPointsIn = Mapping[int, Union[Value, bool, int]]

class PartitionPoints(Dict[int, Value]):
    def __init__(self, partition_points: Optional[PartitionPointsIn] = None):
        ...

    def like(self,
             name: Optional[str] = None,
             src_loc_at: int = 0) -> 'PartitionPoints':
        ...

    def eq(self, rhs: 'PartitionPoints') -> Iterable[Assign]:
        ...

    def as_mask(self, width: int) -> Value:
        bits: List[Union[Value, bool]]

    def get_max_partition_count(self, width: int) -> int:
        ...

    def fits_in_width(self, width: int) -> bool:
        ...


@final
class FullAdder(Elaboratable):
    def __init__(self, width: int):
        ...

    def elaborate(self, platform: Any) -> Module:
        ...


@final
class PartitionedAdder(Elaboratable):
    def __init__(self, width: int, partition_points: PartitionPointsIn):
        ...

    def elaborate(self, platform: Any) -> Module:
        ...


@final
class AddReduce(Elaboratable):
    def __init__(self,
        ...

    @staticmethod
    def get_max_level(input_count: int) -> int:
        ...

    def next_register_levels(self) -> Iterable[int]:
        ...

    @staticmethod
    def full_adder_groups(input_count: int) -> range:
        ...

    def elaborate(self, platform: Any) -> Module:
        intermediate_terms: List[Signal]
        def add_intermediate_term(value: Value) -> None:
            ...


class Mul8_16_32_64(Elaboratable):
    def __init__(self, register_levels: Iterable[int] = ()):
        ...

    def _part_byte(self, index: int) -> Value:
        ...

    def elaborate(self, platform: Any) -> Module:
        ...

        def add_term(value: Value,
                     shift: int = 0,
                     enabled: Optional[Value] = None) -> None:
            ...
