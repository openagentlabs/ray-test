from google.protobuf import wrappers_pb2 as _wrappers_pb2
from udpa.annotations import status_pb2 as _status_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SocketCmsgHeaders(_message.Message):
    __slots__ = ("level", "type", "expected_size")
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_SIZE_FIELD_NUMBER: _ClassVar[int]
    level: _wrappers_pb2.UInt32Value
    type: _wrappers_pb2.UInt32Value
    expected_size: int
    def __init__(self, level: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ..., type: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ..., expected_size: _Optional[int] = ...) -> None: ...
