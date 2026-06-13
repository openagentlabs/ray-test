from google.protobuf import wrappers_pb2 as _wrappers_pb2
from udpa.annotations import status_pb2 as _status_pb2
from validate import validate_pb2 as _validate_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class UdpSocketConfig(_message.Message):
    __slots__ = ("max_rx_datagram_size", "prefer_gro")
    MAX_RX_DATAGRAM_SIZE_FIELD_NUMBER: _ClassVar[int]
    PREFER_GRO_FIELD_NUMBER: _ClassVar[int]
    max_rx_datagram_size: _wrappers_pb2.UInt64Value
    prefer_gro: _wrappers_pb2.BoolValue
    def __init__(self, max_rx_datagram_size: _Optional[_Union[_wrappers_pb2.UInt64Value, _Mapping]] = ..., prefer_gro: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ...) -> None: ...
