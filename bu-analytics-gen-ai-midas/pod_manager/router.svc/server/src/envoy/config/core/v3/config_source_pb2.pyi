import datetime

from envoy.config.core.v3 import base_pb2 as _base_pb2
from envoy.config.core.v3 import extension_pb2 as _extension_pb2
from envoy.config.core.v3 import grpc_service_pb2 as _grpc_service_pb2
from google.protobuf import any_pb2 as _any_pb2
from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf import wrappers_pb2 as _wrappers_pb2
from xds.core.v3 import authority_pb2 as _authority_pb2
from envoy.annotations import deprecation_pb2 as _deprecation_pb2
from udpa.annotations import status_pb2 as _status_pb2
from udpa.annotations import versioning_pb2 as _versioning_pb2
from validate import validate_pb2 as _validate_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ApiVersion(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    AUTO: _ClassVar[ApiVersion]
    V2: _ClassVar[ApiVersion]
    V3: _ClassVar[ApiVersion]
AUTO: ApiVersion
V2: ApiVersion
V3: ApiVersion

class ApiConfigSource(_message.Message):
    __slots__ = ("api_type", "transport_api_version", "cluster_names", "grpc_services", "refresh_delay", "request_timeout", "rate_limit_settings", "set_node_on_first_message_only", "config_validators")
    class ApiType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        DEPRECATED_AND_UNAVAILABLE_DO_NOT_USE: _ClassVar[ApiConfigSource.ApiType]
        REST: _ClassVar[ApiConfigSource.ApiType]
        GRPC: _ClassVar[ApiConfigSource.ApiType]
        DELTA_GRPC: _ClassVar[ApiConfigSource.ApiType]
        AGGREGATED_GRPC: _ClassVar[ApiConfigSource.ApiType]
        AGGREGATED_DELTA_GRPC: _ClassVar[ApiConfigSource.ApiType]
    DEPRECATED_AND_UNAVAILABLE_DO_NOT_USE: ApiConfigSource.ApiType
    REST: ApiConfigSource.ApiType
    GRPC: ApiConfigSource.ApiType
    DELTA_GRPC: ApiConfigSource.ApiType
    AGGREGATED_GRPC: ApiConfigSource.ApiType
    AGGREGATED_DELTA_GRPC: ApiConfigSource.ApiType
    API_TYPE_FIELD_NUMBER: _ClassVar[int]
    TRANSPORT_API_VERSION_FIELD_NUMBER: _ClassVar[int]
    CLUSTER_NAMES_FIELD_NUMBER: _ClassVar[int]
    GRPC_SERVICES_FIELD_NUMBER: _ClassVar[int]
    REFRESH_DELAY_FIELD_NUMBER: _ClassVar[int]
    REQUEST_TIMEOUT_FIELD_NUMBER: _ClassVar[int]
    RATE_LIMIT_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    SET_NODE_ON_FIRST_MESSAGE_ONLY_FIELD_NUMBER: _ClassVar[int]
    CONFIG_VALIDATORS_FIELD_NUMBER: _ClassVar[int]
    api_type: ApiConfigSource.ApiType
    transport_api_version: ApiVersion
    cluster_names: _containers.RepeatedScalarFieldContainer[str]
    grpc_services: _containers.RepeatedCompositeFieldContainer[_grpc_service_pb2.GrpcService]
    refresh_delay: _duration_pb2.Duration
    request_timeout: _duration_pb2.Duration
    rate_limit_settings: RateLimitSettings
    set_node_on_first_message_only: bool
    config_validators: _containers.RepeatedCompositeFieldContainer[_extension_pb2.TypedExtensionConfig]
    def __init__(self, api_type: _Optional[_Union[ApiConfigSource.ApiType, str]] = ..., transport_api_version: _Optional[_Union[ApiVersion, str]] = ..., cluster_names: _Optional[_Iterable[str]] = ..., grpc_services: _Optional[_Iterable[_Union[_grpc_service_pb2.GrpcService, _Mapping]]] = ..., refresh_delay: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., request_timeout: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., rate_limit_settings: _Optional[_Union[RateLimitSettings, _Mapping]] = ..., set_node_on_first_message_only: bool = ..., config_validators: _Optional[_Iterable[_Union[_extension_pb2.TypedExtensionConfig, _Mapping]]] = ...) -> None: ...

class AggregatedConfigSource(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SelfConfigSource(_message.Message):
    __slots__ = ("transport_api_version",)
    TRANSPORT_API_VERSION_FIELD_NUMBER: _ClassVar[int]
    transport_api_version: ApiVersion
    def __init__(self, transport_api_version: _Optional[_Union[ApiVersion, str]] = ...) -> None: ...

class RateLimitSettings(_message.Message):
    __slots__ = ("max_tokens", "fill_rate")
    MAX_TOKENS_FIELD_NUMBER: _ClassVar[int]
    FILL_RATE_FIELD_NUMBER: _ClassVar[int]
    max_tokens: _wrappers_pb2.UInt32Value
    fill_rate: _wrappers_pb2.DoubleValue
    def __init__(self, max_tokens: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ..., fill_rate: _Optional[_Union[_wrappers_pb2.DoubleValue, _Mapping]] = ...) -> None: ...

class PathConfigSource(_message.Message):
    __slots__ = ("path", "watched_directory")
    PATH_FIELD_NUMBER: _ClassVar[int]
    WATCHED_DIRECTORY_FIELD_NUMBER: _ClassVar[int]
    path: str
    watched_directory: _base_pb2.WatchedDirectory
    def __init__(self, path: _Optional[str] = ..., watched_directory: _Optional[_Union[_base_pb2.WatchedDirectory, _Mapping]] = ...) -> None: ...

class ConfigSource(_message.Message):
    __slots__ = ("authorities", "path", "path_config_source", "api_config_source", "ads", "self", "initial_fetch_timeout", "resource_api_version")
    AUTHORITIES_FIELD_NUMBER: _ClassVar[int]
    PATH_FIELD_NUMBER: _ClassVar[int]
    PATH_CONFIG_SOURCE_FIELD_NUMBER: _ClassVar[int]
    API_CONFIG_SOURCE_FIELD_NUMBER: _ClassVar[int]
    ADS_FIELD_NUMBER: _ClassVar[int]
    SELF_FIELD_NUMBER: _ClassVar[int]
    INITIAL_FETCH_TIMEOUT_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_API_VERSION_FIELD_NUMBER: _ClassVar[int]
    authorities: _containers.RepeatedCompositeFieldContainer[_authority_pb2.Authority]
    path: str
    path_config_source: PathConfigSource
    api_config_source: ApiConfigSource
    ads: AggregatedConfigSource
    self: SelfConfigSource
    initial_fetch_timeout: _duration_pb2.Duration
    resource_api_version: ApiVersion
    def __init__(self_, authorities: _Optional[_Iterable[_Union[_authority_pb2.Authority, _Mapping]]] = ..., path: _Optional[str] = ..., path_config_source: _Optional[_Union[PathConfigSource, _Mapping]] = ..., api_config_source: _Optional[_Union[ApiConfigSource, _Mapping]] = ..., ads: _Optional[_Union[AggregatedConfigSource, _Mapping]] = ..., self: _Optional[_Union[SelfConfigSource, _Mapping]] = ..., initial_fetch_timeout: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., resource_api_version: _Optional[_Union[ApiVersion, str]] = ...) -> None: ...

class ExtensionConfigSource(_message.Message):
    __slots__ = ("config_source", "default_config", "apply_default_config_without_warming", "type_urls")
    CONFIG_SOURCE_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_CONFIG_FIELD_NUMBER: _ClassVar[int]
    APPLY_DEFAULT_CONFIG_WITHOUT_WARMING_FIELD_NUMBER: _ClassVar[int]
    TYPE_URLS_FIELD_NUMBER: _ClassVar[int]
    config_source: ConfigSource
    default_config: _any_pb2.Any
    apply_default_config_without_warming: bool
    type_urls: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, config_source: _Optional[_Union[ConfigSource, _Mapping]] = ..., default_config: _Optional[_Union[_any_pb2.Any, _Mapping]] = ..., apply_default_config_without_warming: bool = ..., type_urls: _Optional[_Iterable[str]] = ...) -> None: ...
