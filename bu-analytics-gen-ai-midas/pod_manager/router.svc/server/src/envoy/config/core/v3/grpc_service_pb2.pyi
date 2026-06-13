import datetime

from envoy.config.core.v3 import base_pb2 as _base_pb2
from google.protobuf import any_pb2 as _any_pb2
from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf import empty_pb2 as _empty_pb2
from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf import wrappers_pb2 as _wrappers_pb2
from udpa.annotations import sensitive_pb2 as _sensitive_pb2
from udpa.annotations import status_pb2 as _status_pb2
from udpa.annotations import versioning_pb2 as _versioning_pb2
from validate import validate_pb2 as _validate_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GrpcService(_message.Message):
    __slots__ = ("envoy_grpc", "google_grpc", "timeout", "initial_metadata", "retry_policy")
    class EnvoyGrpc(_message.Message):
        __slots__ = ("cluster_name", "authority", "retry_policy", "max_receive_message_length", "skip_envoy_headers")
        CLUSTER_NAME_FIELD_NUMBER: _ClassVar[int]
        AUTHORITY_FIELD_NUMBER: _ClassVar[int]
        RETRY_POLICY_FIELD_NUMBER: _ClassVar[int]
        MAX_RECEIVE_MESSAGE_LENGTH_FIELD_NUMBER: _ClassVar[int]
        SKIP_ENVOY_HEADERS_FIELD_NUMBER: _ClassVar[int]
        cluster_name: str
        authority: str
        retry_policy: _base_pb2.RetryPolicy
        max_receive_message_length: _wrappers_pb2.UInt32Value
        skip_envoy_headers: bool
        def __init__(self, cluster_name: _Optional[str] = ..., authority: _Optional[str] = ..., retry_policy: _Optional[_Union[_base_pb2.RetryPolicy, _Mapping]] = ..., max_receive_message_length: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ..., skip_envoy_headers: bool = ...) -> None: ...
    class GoogleGrpc(_message.Message):
        __slots__ = ("target_uri", "channel_credentials", "call_credentials", "stat_prefix", "credentials_factory_name", "config", "per_stream_buffer_limit_bytes", "channel_args")
        class SslCredentials(_message.Message):
            __slots__ = ("root_certs", "private_key", "cert_chain")
            ROOT_CERTS_FIELD_NUMBER: _ClassVar[int]
            PRIVATE_KEY_FIELD_NUMBER: _ClassVar[int]
            CERT_CHAIN_FIELD_NUMBER: _ClassVar[int]
            root_certs: _base_pb2.DataSource
            private_key: _base_pb2.DataSource
            cert_chain: _base_pb2.DataSource
            def __init__(self, root_certs: _Optional[_Union[_base_pb2.DataSource, _Mapping]] = ..., private_key: _Optional[_Union[_base_pb2.DataSource, _Mapping]] = ..., cert_chain: _Optional[_Union[_base_pb2.DataSource, _Mapping]] = ...) -> None: ...
        class GoogleLocalCredentials(_message.Message):
            __slots__ = ()
            def __init__(self) -> None: ...
        class ChannelCredentials(_message.Message):
            __slots__ = ("ssl_credentials", "google_default", "local_credentials")
            SSL_CREDENTIALS_FIELD_NUMBER: _ClassVar[int]
            GOOGLE_DEFAULT_FIELD_NUMBER: _ClassVar[int]
            LOCAL_CREDENTIALS_FIELD_NUMBER: _ClassVar[int]
            ssl_credentials: GrpcService.GoogleGrpc.SslCredentials
            google_default: _empty_pb2.Empty
            local_credentials: GrpcService.GoogleGrpc.GoogleLocalCredentials
            def __init__(self, ssl_credentials: _Optional[_Union[GrpcService.GoogleGrpc.SslCredentials, _Mapping]] = ..., google_default: _Optional[_Union[_empty_pb2.Empty, _Mapping]] = ..., local_credentials: _Optional[_Union[GrpcService.GoogleGrpc.GoogleLocalCredentials, _Mapping]] = ...) -> None: ...
        class CallCredentials(_message.Message):
            __slots__ = ("access_token", "google_compute_engine", "google_refresh_token", "service_account_jwt_access", "google_iam", "from_plugin", "sts_service")
            class ServiceAccountJWTAccessCredentials(_message.Message):
                __slots__ = ("json_key", "token_lifetime_seconds")
                JSON_KEY_FIELD_NUMBER: _ClassVar[int]
                TOKEN_LIFETIME_SECONDS_FIELD_NUMBER: _ClassVar[int]
                json_key: str
                token_lifetime_seconds: int
                def __init__(self, json_key: _Optional[str] = ..., token_lifetime_seconds: _Optional[int] = ...) -> None: ...
            class GoogleIAMCredentials(_message.Message):
                __slots__ = ("authorization_token", "authority_selector")
                AUTHORIZATION_TOKEN_FIELD_NUMBER: _ClassVar[int]
                AUTHORITY_SELECTOR_FIELD_NUMBER: _ClassVar[int]
                authorization_token: str
                authority_selector: str
                def __init__(self, authorization_token: _Optional[str] = ..., authority_selector: _Optional[str] = ...) -> None: ...
            class MetadataCredentialsFromPlugin(_message.Message):
                __slots__ = ("name", "typed_config")
                NAME_FIELD_NUMBER: _ClassVar[int]
                TYPED_CONFIG_FIELD_NUMBER: _ClassVar[int]
                name: str
                typed_config: _any_pb2.Any
                def __init__(self, name: _Optional[str] = ..., typed_config: _Optional[_Union[_any_pb2.Any, _Mapping]] = ...) -> None: ...
            class StsService(_message.Message):
                __slots__ = ("token_exchange_service_uri", "resource", "audience", "scope", "requested_token_type", "subject_token_path", "subject_token_type", "actor_token_path", "actor_token_type")
                TOKEN_EXCHANGE_SERVICE_URI_FIELD_NUMBER: _ClassVar[int]
                RESOURCE_FIELD_NUMBER: _ClassVar[int]
                AUDIENCE_FIELD_NUMBER: _ClassVar[int]
                SCOPE_FIELD_NUMBER: _ClassVar[int]
                REQUESTED_TOKEN_TYPE_FIELD_NUMBER: _ClassVar[int]
                SUBJECT_TOKEN_PATH_FIELD_NUMBER: _ClassVar[int]
                SUBJECT_TOKEN_TYPE_FIELD_NUMBER: _ClassVar[int]
                ACTOR_TOKEN_PATH_FIELD_NUMBER: _ClassVar[int]
                ACTOR_TOKEN_TYPE_FIELD_NUMBER: _ClassVar[int]
                token_exchange_service_uri: str
                resource: str
                audience: str
                scope: str
                requested_token_type: str
                subject_token_path: str
                subject_token_type: str
                actor_token_path: str
                actor_token_type: str
                def __init__(self, token_exchange_service_uri: _Optional[str] = ..., resource: _Optional[str] = ..., audience: _Optional[str] = ..., scope: _Optional[str] = ..., requested_token_type: _Optional[str] = ..., subject_token_path: _Optional[str] = ..., subject_token_type: _Optional[str] = ..., actor_token_path: _Optional[str] = ..., actor_token_type: _Optional[str] = ...) -> None: ...
            ACCESS_TOKEN_FIELD_NUMBER: _ClassVar[int]
            GOOGLE_COMPUTE_ENGINE_FIELD_NUMBER: _ClassVar[int]
            GOOGLE_REFRESH_TOKEN_FIELD_NUMBER: _ClassVar[int]
            SERVICE_ACCOUNT_JWT_ACCESS_FIELD_NUMBER: _ClassVar[int]
            GOOGLE_IAM_FIELD_NUMBER: _ClassVar[int]
            FROM_PLUGIN_FIELD_NUMBER: _ClassVar[int]
            STS_SERVICE_FIELD_NUMBER: _ClassVar[int]
            access_token: str
            google_compute_engine: _empty_pb2.Empty
            google_refresh_token: str
            service_account_jwt_access: GrpcService.GoogleGrpc.CallCredentials.ServiceAccountJWTAccessCredentials
            google_iam: GrpcService.GoogleGrpc.CallCredentials.GoogleIAMCredentials
            from_plugin: GrpcService.GoogleGrpc.CallCredentials.MetadataCredentialsFromPlugin
            sts_service: GrpcService.GoogleGrpc.CallCredentials.StsService
            def __init__(self, access_token: _Optional[str] = ..., google_compute_engine: _Optional[_Union[_empty_pb2.Empty, _Mapping]] = ..., google_refresh_token: _Optional[str] = ..., service_account_jwt_access: _Optional[_Union[GrpcService.GoogleGrpc.CallCredentials.ServiceAccountJWTAccessCredentials, _Mapping]] = ..., google_iam: _Optional[_Union[GrpcService.GoogleGrpc.CallCredentials.GoogleIAMCredentials, _Mapping]] = ..., from_plugin: _Optional[_Union[GrpcService.GoogleGrpc.CallCredentials.MetadataCredentialsFromPlugin, _Mapping]] = ..., sts_service: _Optional[_Union[GrpcService.GoogleGrpc.CallCredentials.StsService, _Mapping]] = ...) -> None: ...
        class ChannelArgs(_message.Message):
            __slots__ = ("args",)
            class Value(_message.Message):
                __slots__ = ("string_value", "int_value")
                STRING_VALUE_FIELD_NUMBER: _ClassVar[int]
                INT_VALUE_FIELD_NUMBER: _ClassVar[int]
                string_value: str
                int_value: int
                def __init__(self, string_value: _Optional[str] = ..., int_value: _Optional[int] = ...) -> None: ...
            class ArgsEntry(_message.Message):
                __slots__ = ("key", "value")
                KEY_FIELD_NUMBER: _ClassVar[int]
                VALUE_FIELD_NUMBER: _ClassVar[int]
                key: str
                value: GrpcService.GoogleGrpc.ChannelArgs.Value
                def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[GrpcService.GoogleGrpc.ChannelArgs.Value, _Mapping]] = ...) -> None: ...
            ARGS_FIELD_NUMBER: _ClassVar[int]
            args: _containers.MessageMap[str, GrpcService.GoogleGrpc.ChannelArgs.Value]
            def __init__(self, args: _Optional[_Mapping[str, GrpcService.GoogleGrpc.ChannelArgs.Value]] = ...) -> None: ...
        TARGET_URI_FIELD_NUMBER: _ClassVar[int]
        CHANNEL_CREDENTIALS_FIELD_NUMBER: _ClassVar[int]
        CALL_CREDENTIALS_FIELD_NUMBER: _ClassVar[int]
        STAT_PREFIX_FIELD_NUMBER: _ClassVar[int]
        CREDENTIALS_FACTORY_NAME_FIELD_NUMBER: _ClassVar[int]
        CONFIG_FIELD_NUMBER: _ClassVar[int]
        PER_STREAM_BUFFER_LIMIT_BYTES_FIELD_NUMBER: _ClassVar[int]
        CHANNEL_ARGS_FIELD_NUMBER: _ClassVar[int]
        target_uri: str
        channel_credentials: GrpcService.GoogleGrpc.ChannelCredentials
        call_credentials: _containers.RepeatedCompositeFieldContainer[GrpcService.GoogleGrpc.CallCredentials]
        stat_prefix: str
        credentials_factory_name: str
        config: _struct_pb2.Struct
        per_stream_buffer_limit_bytes: _wrappers_pb2.UInt32Value
        channel_args: GrpcService.GoogleGrpc.ChannelArgs
        def __init__(self, target_uri: _Optional[str] = ..., channel_credentials: _Optional[_Union[GrpcService.GoogleGrpc.ChannelCredentials, _Mapping]] = ..., call_credentials: _Optional[_Iterable[_Union[GrpcService.GoogleGrpc.CallCredentials, _Mapping]]] = ..., stat_prefix: _Optional[str] = ..., credentials_factory_name: _Optional[str] = ..., config: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., per_stream_buffer_limit_bytes: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ..., channel_args: _Optional[_Union[GrpcService.GoogleGrpc.ChannelArgs, _Mapping]] = ...) -> None: ...
    ENVOY_GRPC_FIELD_NUMBER: _ClassVar[int]
    GOOGLE_GRPC_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_FIELD_NUMBER: _ClassVar[int]
    INITIAL_METADATA_FIELD_NUMBER: _ClassVar[int]
    RETRY_POLICY_FIELD_NUMBER: _ClassVar[int]
    envoy_grpc: GrpcService.EnvoyGrpc
    google_grpc: GrpcService.GoogleGrpc
    timeout: _duration_pb2.Duration
    initial_metadata: _containers.RepeatedCompositeFieldContainer[_base_pb2.HeaderValue]
    retry_policy: _base_pb2.RetryPolicy
    def __init__(self, envoy_grpc: _Optional[_Union[GrpcService.EnvoyGrpc, _Mapping]] = ..., google_grpc: _Optional[_Union[GrpcService.GoogleGrpc, _Mapping]] = ..., timeout: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., initial_metadata: _Optional[_Iterable[_Union[_base_pb2.HeaderValue, _Mapping]]] = ..., retry_policy: _Optional[_Union[_base_pb2.RetryPolicy, _Mapping]] = ...) -> None: ...
