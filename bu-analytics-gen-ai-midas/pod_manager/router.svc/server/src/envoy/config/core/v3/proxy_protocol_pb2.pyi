from udpa.annotations import status_pb2 as _status_pb2
from validate import validate_pb2 as _validate_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ProxyProtocolPassThroughTLVs(_message.Message):
    __slots__ = ("match_type", "tlv_type")
    class PassTLVsMatchType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        INCLUDE_ALL: _ClassVar[ProxyProtocolPassThroughTLVs.PassTLVsMatchType]
        INCLUDE: _ClassVar[ProxyProtocolPassThroughTLVs.PassTLVsMatchType]
    INCLUDE_ALL: ProxyProtocolPassThroughTLVs.PassTLVsMatchType
    INCLUDE: ProxyProtocolPassThroughTLVs.PassTLVsMatchType
    MATCH_TYPE_FIELD_NUMBER: _ClassVar[int]
    TLV_TYPE_FIELD_NUMBER: _ClassVar[int]
    match_type: ProxyProtocolPassThroughTLVs.PassTLVsMatchType
    tlv_type: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, match_type: _Optional[_Union[ProxyProtocolPassThroughTLVs.PassTLVsMatchType, str]] = ..., tlv_type: _Optional[_Iterable[int]] = ...) -> None: ...

class TlvEntry(_message.Message):
    __slots__ = ("type", "value")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    type: int
    value: bytes
    def __init__(self, type: _Optional[int] = ..., value: _Optional[bytes] = ...) -> None: ...

class ProxyProtocolConfig(_message.Message):
    __slots__ = ("version", "pass_through_tlvs", "added_tlvs")
    class Version(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        V1: _ClassVar[ProxyProtocolConfig.Version]
        V2: _ClassVar[ProxyProtocolConfig.Version]
    V1: ProxyProtocolConfig.Version
    V2: ProxyProtocolConfig.Version
    VERSION_FIELD_NUMBER: _ClassVar[int]
    PASS_THROUGH_TLVS_FIELD_NUMBER: _ClassVar[int]
    ADDED_TLVS_FIELD_NUMBER: _ClassVar[int]
    version: ProxyProtocolConfig.Version
    pass_through_tlvs: ProxyProtocolPassThroughTLVs
    added_tlvs: _containers.RepeatedCompositeFieldContainer[TlvEntry]
    def __init__(self, version: _Optional[_Union[ProxyProtocolConfig.Version, str]] = ..., pass_through_tlvs: _Optional[_Union[ProxyProtocolPassThroughTLVs, _Mapping]] = ..., added_tlvs: _Optional[_Iterable[_Union[TlvEntry, _Mapping]]] = ...) -> None: ...

class PerHostConfig(_message.Message):
    __slots__ = ("added_tlvs",)
    ADDED_TLVS_FIELD_NUMBER: _ClassVar[int]
    added_tlvs: _containers.RepeatedCompositeFieldContainer[TlvEntry]
    def __init__(self, added_tlvs: _Optional[_Iterable[_Union[TlvEntry, _Mapping]]] = ...) -> None: ...
