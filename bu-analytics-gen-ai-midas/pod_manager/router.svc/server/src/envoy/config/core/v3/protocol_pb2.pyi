import datetime

from envoy.config.core.v3 import extension_pb2 as _extension_pb2
from envoy.type.matcher.v3 import string_pb2 as _string_pb2
from envoy.type.v3 import percent_pb2 as _percent_pb2
from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf import wrappers_pb2 as _wrappers_pb2
from xds.annotations.v3 import status_pb2 as _status_pb2
from envoy.annotations import deprecation_pb2 as _deprecation_pb2
from udpa.annotations import status_pb2 as _status_pb2_1
from udpa.annotations import versioning_pb2 as _versioning_pb2
from validate import validate_pb2 as _validate_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class TcpProtocolOptions(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class QuicKeepAliveSettings(_message.Message):
    __slots__ = ("max_interval", "initial_interval")
    MAX_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    INITIAL_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    max_interval: _duration_pb2.Duration
    initial_interval: _duration_pb2.Duration
    def __init__(self, max_interval: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., initial_interval: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...

class QuicProtocolOptions(_message.Message):
    __slots__ = ("max_concurrent_streams", "initial_stream_window_size", "initial_connection_window_size", "num_timeouts_to_trigger_port_migration", "connection_keepalive", "connection_options", "client_connection_options", "idle_network_timeout", "max_packet_length")
    MAX_CONCURRENT_STREAMS_FIELD_NUMBER: _ClassVar[int]
    INITIAL_STREAM_WINDOW_SIZE_FIELD_NUMBER: _ClassVar[int]
    INITIAL_CONNECTION_WINDOW_SIZE_FIELD_NUMBER: _ClassVar[int]
    NUM_TIMEOUTS_TO_TRIGGER_PORT_MIGRATION_FIELD_NUMBER: _ClassVar[int]
    CONNECTION_KEEPALIVE_FIELD_NUMBER: _ClassVar[int]
    CONNECTION_OPTIONS_FIELD_NUMBER: _ClassVar[int]
    CLIENT_CONNECTION_OPTIONS_FIELD_NUMBER: _ClassVar[int]
    IDLE_NETWORK_TIMEOUT_FIELD_NUMBER: _ClassVar[int]
    MAX_PACKET_LENGTH_FIELD_NUMBER: _ClassVar[int]
    max_concurrent_streams: _wrappers_pb2.UInt32Value
    initial_stream_window_size: _wrappers_pb2.UInt32Value
    initial_connection_window_size: _wrappers_pb2.UInt32Value
    num_timeouts_to_trigger_port_migration: _wrappers_pb2.UInt32Value
    connection_keepalive: QuicKeepAliveSettings
    connection_options: str
    client_connection_options: str
    idle_network_timeout: _duration_pb2.Duration
    max_packet_length: _wrappers_pb2.UInt64Value
    def __init__(self, max_concurrent_streams: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ..., initial_stream_window_size: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ..., initial_connection_window_size: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ..., num_timeouts_to_trigger_port_migration: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ..., connection_keepalive: _Optional[_Union[QuicKeepAliveSettings, _Mapping]] = ..., connection_options: _Optional[str] = ..., client_connection_options: _Optional[str] = ..., idle_network_timeout: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., max_packet_length: _Optional[_Union[_wrappers_pb2.UInt64Value, _Mapping]] = ...) -> None: ...

class UpstreamHttpProtocolOptions(_message.Message):
    __slots__ = ("auto_sni", "auto_san_validation", "override_auto_sni_header")
    AUTO_SNI_FIELD_NUMBER: _ClassVar[int]
    AUTO_SAN_VALIDATION_FIELD_NUMBER: _ClassVar[int]
    OVERRIDE_AUTO_SNI_HEADER_FIELD_NUMBER: _ClassVar[int]
    auto_sni: bool
    auto_san_validation: bool
    override_auto_sni_header: str
    def __init__(self, auto_sni: bool = ..., auto_san_validation: bool = ..., override_auto_sni_header: _Optional[str] = ...) -> None: ...

class AlternateProtocolsCacheOptions(_message.Message):
    __slots__ = ("name", "max_entries", "key_value_store_config", "prepopulated_entries", "canonical_suffixes")
    class AlternateProtocolsCacheEntry(_message.Message):
        __slots__ = ("hostname", "port")
        HOSTNAME_FIELD_NUMBER: _ClassVar[int]
        PORT_FIELD_NUMBER: _ClassVar[int]
        hostname: str
        port: int
        def __init__(self, hostname: _Optional[str] = ..., port: _Optional[int] = ...) -> None: ...
    NAME_FIELD_NUMBER: _ClassVar[int]
    MAX_ENTRIES_FIELD_NUMBER: _ClassVar[int]
    KEY_VALUE_STORE_CONFIG_FIELD_NUMBER: _ClassVar[int]
    PREPOPULATED_ENTRIES_FIELD_NUMBER: _ClassVar[int]
    CANONICAL_SUFFIXES_FIELD_NUMBER: _ClassVar[int]
    name: str
    max_entries: _wrappers_pb2.UInt32Value
    key_value_store_config: _extension_pb2.TypedExtensionConfig
    prepopulated_entries: _containers.RepeatedCompositeFieldContainer[AlternateProtocolsCacheOptions.AlternateProtocolsCacheEntry]
    canonical_suffixes: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, name: _Optional[str] = ..., max_entries: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ..., key_value_store_config: _Optional[_Union[_extension_pb2.TypedExtensionConfig, _Mapping]] = ..., prepopulated_entries: _Optional[_Iterable[_Union[AlternateProtocolsCacheOptions.AlternateProtocolsCacheEntry, _Mapping]]] = ..., canonical_suffixes: _Optional[_Iterable[str]] = ...) -> None: ...

class HttpProtocolOptions(_message.Message):
    __slots__ = ("idle_timeout", "max_connection_duration", "max_headers_count", "max_response_headers_kb", "max_stream_duration", "headers_with_underscores_action", "max_requests_per_connection")
    class HeadersWithUnderscoresAction(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        ALLOW: _ClassVar[HttpProtocolOptions.HeadersWithUnderscoresAction]
        REJECT_REQUEST: _ClassVar[HttpProtocolOptions.HeadersWithUnderscoresAction]
        DROP_HEADER: _ClassVar[HttpProtocolOptions.HeadersWithUnderscoresAction]
    ALLOW: HttpProtocolOptions.HeadersWithUnderscoresAction
    REJECT_REQUEST: HttpProtocolOptions.HeadersWithUnderscoresAction
    DROP_HEADER: HttpProtocolOptions.HeadersWithUnderscoresAction
    IDLE_TIMEOUT_FIELD_NUMBER: _ClassVar[int]
    MAX_CONNECTION_DURATION_FIELD_NUMBER: _ClassVar[int]
    MAX_HEADERS_COUNT_FIELD_NUMBER: _ClassVar[int]
    MAX_RESPONSE_HEADERS_KB_FIELD_NUMBER: _ClassVar[int]
    MAX_STREAM_DURATION_FIELD_NUMBER: _ClassVar[int]
    HEADERS_WITH_UNDERSCORES_ACTION_FIELD_NUMBER: _ClassVar[int]
    MAX_REQUESTS_PER_CONNECTION_FIELD_NUMBER: _ClassVar[int]
    idle_timeout: _duration_pb2.Duration
    max_connection_duration: _duration_pb2.Duration
    max_headers_count: _wrappers_pb2.UInt32Value
    max_response_headers_kb: _wrappers_pb2.UInt32Value
    max_stream_duration: _duration_pb2.Duration
    headers_with_underscores_action: HttpProtocolOptions.HeadersWithUnderscoresAction
    max_requests_per_connection: _wrappers_pb2.UInt32Value
    def __init__(self, idle_timeout: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., max_connection_duration: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., max_headers_count: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ..., max_response_headers_kb: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ..., max_stream_duration: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., headers_with_underscores_action: _Optional[_Union[HttpProtocolOptions.HeadersWithUnderscoresAction, str]] = ..., max_requests_per_connection: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ...) -> None: ...

class Http1ProtocolOptions(_message.Message):
    __slots__ = ("allow_absolute_url", "accept_http_10", "default_host_for_http_10", "header_key_format", "enable_trailers", "allow_chunked_length", "override_stream_error_on_invalid_http_message", "send_fully_qualified_url", "use_balsa_parser", "allow_custom_methods", "ignore_http_11_upgrade")
    class HeaderKeyFormat(_message.Message):
        __slots__ = ("proper_case_words", "stateful_formatter")
        class ProperCaseWords(_message.Message):
            __slots__ = ()
            def __init__(self) -> None: ...
        PROPER_CASE_WORDS_FIELD_NUMBER: _ClassVar[int]
        STATEFUL_FORMATTER_FIELD_NUMBER: _ClassVar[int]
        proper_case_words: Http1ProtocolOptions.HeaderKeyFormat.ProperCaseWords
        stateful_formatter: _extension_pb2.TypedExtensionConfig
        def __init__(self, proper_case_words: _Optional[_Union[Http1ProtocolOptions.HeaderKeyFormat.ProperCaseWords, _Mapping]] = ..., stateful_formatter: _Optional[_Union[_extension_pb2.TypedExtensionConfig, _Mapping]] = ...) -> None: ...
    ALLOW_ABSOLUTE_URL_FIELD_NUMBER: _ClassVar[int]
    ACCEPT_HTTP_10_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_HOST_FOR_HTTP_10_FIELD_NUMBER: _ClassVar[int]
    HEADER_KEY_FORMAT_FIELD_NUMBER: _ClassVar[int]
    ENABLE_TRAILERS_FIELD_NUMBER: _ClassVar[int]
    ALLOW_CHUNKED_LENGTH_FIELD_NUMBER: _ClassVar[int]
    OVERRIDE_STREAM_ERROR_ON_INVALID_HTTP_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    SEND_FULLY_QUALIFIED_URL_FIELD_NUMBER: _ClassVar[int]
    USE_BALSA_PARSER_FIELD_NUMBER: _ClassVar[int]
    ALLOW_CUSTOM_METHODS_FIELD_NUMBER: _ClassVar[int]
    IGNORE_HTTP_11_UPGRADE_FIELD_NUMBER: _ClassVar[int]
    allow_absolute_url: _wrappers_pb2.BoolValue
    accept_http_10: bool
    default_host_for_http_10: str
    header_key_format: Http1ProtocolOptions.HeaderKeyFormat
    enable_trailers: bool
    allow_chunked_length: bool
    override_stream_error_on_invalid_http_message: _wrappers_pb2.BoolValue
    send_fully_qualified_url: bool
    use_balsa_parser: _wrappers_pb2.BoolValue
    allow_custom_methods: bool
    ignore_http_11_upgrade: _containers.RepeatedCompositeFieldContainer[_string_pb2.StringMatcher]
    def __init__(self, allow_absolute_url: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., accept_http_10: bool = ..., default_host_for_http_10: _Optional[str] = ..., header_key_format: _Optional[_Union[Http1ProtocolOptions.HeaderKeyFormat, _Mapping]] = ..., enable_trailers: bool = ..., allow_chunked_length: bool = ..., override_stream_error_on_invalid_http_message: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., send_fully_qualified_url: bool = ..., use_balsa_parser: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., allow_custom_methods: bool = ..., ignore_http_11_upgrade: _Optional[_Iterable[_Union[_string_pb2.StringMatcher, _Mapping]]] = ...) -> None: ...

class KeepaliveSettings(_message.Message):
    __slots__ = ("interval", "timeout", "interval_jitter", "connection_idle_interval")
    INTERVAL_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_FIELD_NUMBER: _ClassVar[int]
    INTERVAL_JITTER_FIELD_NUMBER: _ClassVar[int]
    CONNECTION_IDLE_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    interval: _duration_pb2.Duration
    timeout: _duration_pb2.Duration
    interval_jitter: _percent_pb2.Percent
    connection_idle_interval: _duration_pb2.Duration
    def __init__(self, interval: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., timeout: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., interval_jitter: _Optional[_Union[_percent_pb2.Percent, _Mapping]] = ..., connection_idle_interval: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...

class Http2ProtocolOptions(_message.Message):
    __slots__ = ("hpack_table_size", "max_concurrent_streams", "initial_stream_window_size", "initial_connection_window_size", "allow_connect", "allow_metadata", "max_outbound_frames", "max_outbound_control_frames", "max_consecutive_inbound_frames_with_empty_payload", "max_inbound_priority_frames_per_stream", "max_inbound_window_update_frames_per_data_frame_sent", "stream_error_on_invalid_http_messaging", "override_stream_error_on_invalid_http_message", "custom_settings_parameters", "connection_keepalive", "use_oghttp2_codec", "max_metadata_size")
    class SettingsParameter(_message.Message):
        __slots__ = ("identifier", "value")
        IDENTIFIER_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        identifier: _wrappers_pb2.UInt32Value
        value: _wrappers_pb2.UInt32Value
        def __init__(self, identifier: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ..., value: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ...) -> None: ...
    HPACK_TABLE_SIZE_FIELD_NUMBER: _ClassVar[int]
    MAX_CONCURRENT_STREAMS_FIELD_NUMBER: _ClassVar[int]
    INITIAL_STREAM_WINDOW_SIZE_FIELD_NUMBER: _ClassVar[int]
    INITIAL_CONNECTION_WINDOW_SIZE_FIELD_NUMBER: _ClassVar[int]
    ALLOW_CONNECT_FIELD_NUMBER: _ClassVar[int]
    ALLOW_METADATA_FIELD_NUMBER: _ClassVar[int]
    MAX_OUTBOUND_FRAMES_FIELD_NUMBER: _ClassVar[int]
    MAX_OUTBOUND_CONTROL_FRAMES_FIELD_NUMBER: _ClassVar[int]
    MAX_CONSECUTIVE_INBOUND_FRAMES_WITH_EMPTY_PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    MAX_INBOUND_PRIORITY_FRAMES_PER_STREAM_FIELD_NUMBER: _ClassVar[int]
    MAX_INBOUND_WINDOW_UPDATE_FRAMES_PER_DATA_FRAME_SENT_FIELD_NUMBER: _ClassVar[int]
    STREAM_ERROR_ON_INVALID_HTTP_MESSAGING_FIELD_NUMBER: _ClassVar[int]
    OVERRIDE_STREAM_ERROR_ON_INVALID_HTTP_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    CUSTOM_SETTINGS_PARAMETERS_FIELD_NUMBER: _ClassVar[int]
    CONNECTION_KEEPALIVE_FIELD_NUMBER: _ClassVar[int]
    USE_OGHTTP2_CODEC_FIELD_NUMBER: _ClassVar[int]
    MAX_METADATA_SIZE_FIELD_NUMBER: _ClassVar[int]
    hpack_table_size: _wrappers_pb2.UInt32Value
    max_concurrent_streams: _wrappers_pb2.UInt32Value
    initial_stream_window_size: _wrappers_pb2.UInt32Value
    initial_connection_window_size: _wrappers_pb2.UInt32Value
    allow_connect: bool
    allow_metadata: bool
    max_outbound_frames: _wrappers_pb2.UInt32Value
    max_outbound_control_frames: _wrappers_pb2.UInt32Value
    max_consecutive_inbound_frames_with_empty_payload: _wrappers_pb2.UInt32Value
    max_inbound_priority_frames_per_stream: _wrappers_pb2.UInt32Value
    max_inbound_window_update_frames_per_data_frame_sent: _wrappers_pb2.UInt32Value
    stream_error_on_invalid_http_messaging: bool
    override_stream_error_on_invalid_http_message: _wrappers_pb2.BoolValue
    custom_settings_parameters: _containers.RepeatedCompositeFieldContainer[Http2ProtocolOptions.SettingsParameter]
    connection_keepalive: KeepaliveSettings
    use_oghttp2_codec: _wrappers_pb2.BoolValue
    max_metadata_size: _wrappers_pb2.UInt64Value
    def __init__(self, hpack_table_size: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ..., max_concurrent_streams: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ..., initial_stream_window_size: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ..., initial_connection_window_size: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ..., allow_connect: bool = ..., allow_metadata: bool = ..., max_outbound_frames: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ..., max_outbound_control_frames: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ..., max_consecutive_inbound_frames_with_empty_payload: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ..., max_inbound_priority_frames_per_stream: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ..., max_inbound_window_update_frames_per_data_frame_sent: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ..., stream_error_on_invalid_http_messaging: bool = ..., override_stream_error_on_invalid_http_message: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., custom_settings_parameters: _Optional[_Iterable[_Union[Http2ProtocolOptions.SettingsParameter, _Mapping]]] = ..., connection_keepalive: _Optional[_Union[KeepaliveSettings, _Mapping]] = ..., use_oghttp2_codec: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., max_metadata_size: _Optional[_Union[_wrappers_pb2.UInt64Value, _Mapping]] = ...) -> None: ...

class GrpcProtocolOptions(_message.Message):
    __slots__ = ("http2_protocol_options",)
    HTTP2_PROTOCOL_OPTIONS_FIELD_NUMBER: _ClassVar[int]
    http2_protocol_options: Http2ProtocolOptions
    def __init__(self, http2_protocol_options: _Optional[_Union[Http2ProtocolOptions, _Mapping]] = ...) -> None: ...

class Http3ProtocolOptions(_message.Message):
    __slots__ = ("quic_protocol_options", "override_stream_error_on_invalid_http_message", "allow_extended_connect", "allow_metadata", "disable_qpack")
    QUIC_PROTOCOL_OPTIONS_FIELD_NUMBER: _ClassVar[int]
    OVERRIDE_STREAM_ERROR_ON_INVALID_HTTP_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    ALLOW_EXTENDED_CONNECT_FIELD_NUMBER: _ClassVar[int]
    ALLOW_METADATA_FIELD_NUMBER: _ClassVar[int]
    DISABLE_QPACK_FIELD_NUMBER: _ClassVar[int]
    quic_protocol_options: QuicProtocolOptions
    override_stream_error_on_invalid_http_message: _wrappers_pb2.BoolValue
    allow_extended_connect: bool
    allow_metadata: bool
    disable_qpack: bool
    def __init__(self, quic_protocol_options: _Optional[_Union[QuicProtocolOptions, _Mapping]] = ..., override_stream_error_on_invalid_http_message: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., allow_extended_connect: bool = ..., allow_metadata: bool = ..., disable_qpack: bool = ...) -> None: ...

class SchemeHeaderTransformation(_message.Message):
    __slots__ = ("scheme_to_overwrite", "match_upstream")
    SCHEME_TO_OVERWRITE_FIELD_NUMBER: _ClassVar[int]
    MATCH_UPSTREAM_FIELD_NUMBER: _ClassVar[int]
    scheme_to_overwrite: str
    match_upstream: bool
    def __init__(self, scheme_to_overwrite: _Optional[str] = ..., match_upstream: bool = ...) -> None: ...
