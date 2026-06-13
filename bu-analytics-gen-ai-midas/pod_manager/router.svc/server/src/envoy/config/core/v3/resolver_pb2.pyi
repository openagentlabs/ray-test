from envoy.config.core.v3 import address_pb2 as _address_pb2
from udpa.annotations import status_pb2 as _status_pb2
from validate import validate_pb2 as _validate_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class DnsResolverOptions(_message.Message):
    __slots__ = ("use_tcp_for_dns_lookups", "no_default_search_domain")
    USE_TCP_FOR_DNS_LOOKUPS_FIELD_NUMBER: _ClassVar[int]
    NO_DEFAULT_SEARCH_DOMAIN_FIELD_NUMBER: _ClassVar[int]
    use_tcp_for_dns_lookups: bool
    no_default_search_domain: bool
    def __init__(self, use_tcp_for_dns_lookups: bool = ..., no_default_search_domain: bool = ...) -> None: ...

class DnsResolutionConfig(_message.Message):
    __slots__ = ("resolvers", "dns_resolver_options")
    RESOLVERS_FIELD_NUMBER: _ClassVar[int]
    DNS_RESOLVER_OPTIONS_FIELD_NUMBER: _ClassVar[int]
    resolvers: _containers.RepeatedCompositeFieldContainer[_address_pb2.Address]
    dns_resolver_options: DnsResolverOptions
    def __init__(self, resolvers: _Optional[_Iterable[_Union[_address_pb2.Address, _Mapping]]] = ..., dns_resolver_options: _Optional[_Union[DnsResolverOptions, _Mapping]] = ...) -> None: ...
