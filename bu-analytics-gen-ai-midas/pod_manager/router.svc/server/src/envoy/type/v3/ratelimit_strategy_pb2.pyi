from envoy.type.v3 import ratelimit_unit_pb2 as _ratelimit_unit_pb2
from envoy.type.v3 import token_bucket_pb2 as _token_bucket_pb2
from xds.annotations.v3 import status_pb2 as _status_pb2
from udpa.annotations import status_pb2 as _status_pb2_1
from validate import validate_pb2 as _validate_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class RateLimitStrategy(_message.Message):
    __slots__ = ("blanket_rule", "requests_per_time_unit", "token_bucket")
    class BlanketRule(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        ALLOW_ALL: _ClassVar[RateLimitStrategy.BlanketRule]
        DENY_ALL: _ClassVar[RateLimitStrategy.BlanketRule]
    ALLOW_ALL: RateLimitStrategy.BlanketRule
    DENY_ALL: RateLimitStrategy.BlanketRule
    class RequestsPerTimeUnit(_message.Message):
        __slots__ = ("requests_per_time_unit", "time_unit")
        REQUESTS_PER_TIME_UNIT_FIELD_NUMBER: _ClassVar[int]
        TIME_UNIT_FIELD_NUMBER: _ClassVar[int]
        requests_per_time_unit: int
        time_unit: _ratelimit_unit_pb2.RateLimitUnit
        def __init__(self, requests_per_time_unit: _Optional[int] = ..., time_unit: _Optional[_Union[_ratelimit_unit_pb2.RateLimitUnit, str]] = ...) -> None: ...
    BLANKET_RULE_FIELD_NUMBER: _ClassVar[int]
    REQUESTS_PER_TIME_UNIT_FIELD_NUMBER: _ClassVar[int]
    TOKEN_BUCKET_FIELD_NUMBER: _ClassVar[int]
    blanket_rule: RateLimitStrategy.BlanketRule
    requests_per_time_unit: RateLimitStrategy.RequestsPerTimeUnit
    token_bucket: _token_bucket_pb2.TokenBucket
    def __init__(self, blanket_rule: _Optional[_Union[RateLimitStrategy.BlanketRule, str]] = ..., requests_per_time_unit: _Optional[_Union[RateLimitStrategy.RequestsPerTimeUnit, _Mapping]] = ..., token_bucket: _Optional[_Union[_token_bucket_pb2.TokenBucket, _Mapping]] = ...) -> None: ...
