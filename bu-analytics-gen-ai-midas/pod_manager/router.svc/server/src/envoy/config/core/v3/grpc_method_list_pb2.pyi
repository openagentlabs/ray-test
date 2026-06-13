from udpa.annotations import status_pb2 as _status_pb2
from udpa.annotations import versioning_pb2 as _versioning_pb2
from validate import validate_pb2 as _validate_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GrpcMethodList(_message.Message):
    __slots__ = ("services",)
    class Service(_message.Message):
        __slots__ = ("name", "method_names")
        NAME_FIELD_NUMBER: _ClassVar[int]
        METHOD_NAMES_FIELD_NUMBER: _ClassVar[int]
        name: str
        method_names: _containers.RepeatedScalarFieldContainer[str]
        def __init__(self, name: _Optional[str] = ..., method_names: _Optional[_Iterable[str]] = ...) -> None: ...
    SERVICES_FIELD_NUMBER: _ClassVar[int]
    services: _containers.RepeatedCompositeFieldContainer[GrpcMethodList.Service]
    def __init__(self, services: _Optional[_Iterable[_Union[GrpcMethodList.Service, _Mapping]]] = ...) -> None: ...
