from envoy.config.core.v3 import base_pb2 as _base_pb2
from envoy.config.core.v3 import extension_pb2 as _extension_pb2
from google.protobuf import struct_pb2 as _struct_pb2
from envoy.annotations import deprecation_pb2 as _deprecation_pb2
from udpa.annotations import status_pb2 as _status_pb2
from validate import validate_pb2 as _validate_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class JsonFormatOptions(_message.Message):
    __slots__ = ("sort_properties",)
    SORT_PROPERTIES_FIELD_NUMBER: _ClassVar[int]
    sort_properties: bool
    def __init__(self, sort_properties: bool = ...) -> None: ...

class SubstitutionFormatString(_message.Message):
    __slots__ = ("text_format", "json_format", "text_format_source", "omit_empty_values", "content_type", "formatters", "json_format_options")
    TEXT_FORMAT_FIELD_NUMBER: _ClassVar[int]
    JSON_FORMAT_FIELD_NUMBER: _ClassVar[int]
    TEXT_FORMAT_SOURCE_FIELD_NUMBER: _ClassVar[int]
    OMIT_EMPTY_VALUES_FIELD_NUMBER: _ClassVar[int]
    CONTENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    FORMATTERS_FIELD_NUMBER: _ClassVar[int]
    JSON_FORMAT_OPTIONS_FIELD_NUMBER: _ClassVar[int]
    text_format: str
    json_format: _struct_pb2.Struct
    text_format_source: _base_pb2.DataSource
    omit_empty_values: bool
    content_type: str
    formatters: _containers.RepeatedCompositeFieldContainer[_extension_pb2.TypedExtensionConfig]
    json_format_options: JsonFormatOptions
    def __init__(self, text_format: _Optional[str] = ..., json_format: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., text_format_source: _Optional[_Union[_base_pb2.DataSource, _Mapping]] = ..., omit_empty_values: bool = ..., content_type: _Optional[str] = ..., formatters: _Optional[_Iterable[_Union[_extension_pb2.TypedExtensionConfig, _Mapping]]] = ..., json_format_options: _Optional[_Union[JsonFormatOptions, _Mapping]] = ...) -> None: ...
