from udpa.annotations import status_pb2 as _status_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from typing import ClassVar as _ClassVar

DESCRIPTOR: _descriptor.FileDescriptor

class RateLimitUnit(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    UNKNOWN: _ClassVar[RateLimitUnit]
    SECOND: _ClassVar[RateLimitUnit]
    MINUTE: _ClassVar[RateLimitUnit]
    HOUR: _ClassVar[RateLimitUnit]
    DAY: _ClassVar[RateLimitUnit]
    MONTH: _ClassVar[RateLimitUnit]
    YEAR: _ClassVar[RateLimitUnit]
UNKNOWN: RateLimitUnit
SECOND: RateLimitUnit
MINUTE: RateLimitUnit
HOUR: RateLimitUnit
DAY: RateLimitUnit
MONTH: RateLimitUnit
YEAR: RateLimitUnit
