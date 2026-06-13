from udpa.annotations import status_pb2 as _status_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from typing import ClassVar as _ClassVar

DESCRIPTOR: _descriptor.FileDescriptor

class CodecClientType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    HTTP1: _ClassVar[CodecClientType]
    HTTP2: _ClassVar[CodecClientType]
    HTTP3: _ClassVar[CodecClientType]
HTTP1: CodecClientType
HTTP2: CodecClientType
HTTP3: CodecClientType
