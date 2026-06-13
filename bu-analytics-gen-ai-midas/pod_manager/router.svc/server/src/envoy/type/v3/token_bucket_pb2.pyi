import datetime

from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf import wrappers_pb2 as _wrappers_pb2
from udpa.annotations import status_pb2 as _status_pb2
from udpa.annotations import versioning_pb2 as _versioning_pb2
from validate import validate_pb2 as _validate_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class TokenBucket(_message.Message):
    __slots__ = ("max_tokens", "tokens_per_fill", "fill_interval")
    MAX_TOKENS_FIELD_NUMBER: _ClassVar[int]
    TOKENS_PER_FILL_FIELD_NUMBER: _ClassVar[int]
    FILL_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    max_tokens: int
    tokens_per_fill: _wrappers_pb2.UInt32Value
    fill_interval: _duration_pb2.Duration
    def __init__(self, max_tokens: _Optional[int] = ..., tokens_per_fill: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ..., fill_interval: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...
