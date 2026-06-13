from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class AcquireLeaseRequest(_message.Message):
    __slots__ = ("sub",)
    SUB_FIELD_NUMBER: _ClassVar[int]
    sub: str
    def __init__(self, sub: _Optional[str] = ...) -> None: ...

class AcquireLeaseResponse(_message.Message):
    __slots__ = ("pod_id", "pod_dns", "assignment_epoch", "already_leased")
    POD_ID_FIELD_NUMBER: _ClassVar[int]
    POD_DNS_FIELD_NUMBER: _ClassVar[int]
    ASSIGNMENT_EPOCH_FIELD_NUMBER: _ClassVar[int]
    ALREADY_LEASED_FIELD_NUMBER: _ClassVar[int]
    pod_id: str
    pod_dns: str
    assignment_epoch: int
    already_leased: bool
    def __init__(self, pod_id: _Optional[str] = ..., pod_dns: _Optional[str] = ..., assignment_epoch: _Optional[int] = ..., already_leased: bool = ...) -> None: ...

class GetLeaseRequest(_message.Message):
    __slots__ = ("sub",)
    SUB_FIELD_NUMBER: _ClassVar[int]
    sub: str
    def __init__(self, sub: _Optional[str] = ...) -> None: ...

class GetLeaseResponse(_message.Message):
    __slots__ = ("pod_id", "pod_dns", "assignment_epoch")
    POD_ID_FIELD_NUMBER: _ClassVar[int]
    POD_DNS_FIELD_NUMBER: _ClassVar[int]
    ASSIGNMENT_EPOCH_FIELD_NUMBER: _ClassVar[int]
    pod_id: str
    pod_dns: str
    assignment_epoch: int
    def __init__(self, pod_id: _Optional[str] = ..., pod_dns: _Optional[str] = ..., assignment_epoch: _Optional[int] = ...) -> None: ...

class ReleaseLeaseRequest(_message.Message):
    __slots__ = ("sub",)
    SUB_FIELD_NUMBER: _ClassVar[int]
    sub: str
    def __init__(self, sub: _Optional[str] = ...) -> None: ...

class ReleaseLeaseResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetBackendPoolAvailabilityRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetBackendPoolAvailabilityResponse(_message.Message):
    __slots__ = ("free_count", "total_count", "has_capacity")
    FREE_COUNT_FIELD_NUMBER: _ClassVar[int]
    TOTAL_COUNT_FIELD_NUMBER: _ClassVar[int]
    HAS_CAPACITY_FIELD_NUMBER: _ClassVar[int]
    free_count: int
    total_count: int
    has_capacity: bool
    def __init__(self, free_count: _Optional[int] = ..., total_count: _Optional[int] = ..., has_capacity: bool = ...) -> None: ...

class GetPoolStatusRequest(_message.Message):
    __slots__ = ("pool",)
    POOL_FIELD_NUMBER: _ClassVar[int]
    pool: str
    def __init__(self, pool: _Optional[str] = ...) -> None: ...

class PodSummary(_message.Message):
    __slots__ = ("pod_id", "pod_dns", "state", "assigned_sub", "pool")
    POD_ID_FIELD_NUMBER: _ClassVar[int]
    POD_DNS_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    ASSIGNED_SUB_FIELD_NUMBER: _ClassVar[int]
    POOL_FIELD_NUMBER: _ClassVar[int]
    pod_id: str
    pod_dns: str
    state: str
    assigned_sub: str
    pool: str
    def __init__(self, pod_id: _Optional[str] = ..., pod_dns: _Optional[str] = ..., state: _Optional[str] = ..., assigned_sub: _Optional[str] = ..., pool: _Optional[str] = ...) -> None: ...

class GetPoolStatusResponse(_message.Message):
    __slots__ = ("pods", "free_count", "claimed_count")
    PODS_FIELD_NUMBER: _ClassVar[int]
    FREE_COUNT_FIELD_NUMBER: _ClassVar[int]
    CLAIMED_COUNT_FIELD_NUMBER: _ClassVar[int]
    pods: _containers.RepeatedCompositeFieldContainer[PodSummary]
    free_count: int
    claimed_count: int
    def __init__(self, pods: _Optional[_Iterable[_Union[PodSummary, _Mapping]]] = ..., free_count: _Optional[int] = ..., claimed_count: _Optional[int] = ...) -> None: ...

class HeartbeatRequest(_message.Message):
    __slots__ = ("sub", "assignment_epoch")
    SUB_FIELD_NUMBER: _ClassVar[int]
    ASSIGNMENT_EPOCH_FIELD_NUMBER: _ClassVar[int]
    sub: str
    assignment_epoch: int
    def __init__(self, sub: _Optional[str] = ..., assignment_epoch: _Optional[int] = ...) -> None: ...

class HeartbeatResponse(_message.Message):
    __slots__ = ("assignment_epoch",)
    ASSIGNMENT_EPOCH_FIELD_NUMBER: _ClassVar[int]
    assignment_epoch: int
    def __init__(self, assignment_epoch: _Optional[int] = ...) -> None: ...

class GetRuntimeEnvironmentRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ConfigEntry(_message.Message):
    __slots__ = ("key", "value")
    KEY_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    key: str
    value: str
    def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...

class GetRuntimeEnvironmentResponse(_message.Message):
    __slots__ = ("entries",)
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    entries: _containers.RepeatedCompositeFieldContainer[ConfigEntry]
    def __init__(self, entries: _Optional[_Iterable[_Union[ConfigEntry, _Mapping]]] = ...) -> None: ...

class ListServiceConfigRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ServiceConfigEntry(_message.Message):
    __slots__ = ("config_key", "value", "updated_at", "description")
    CONFIG_KEY_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    config_key: str
    value: str
    updated_at: str
    description: str
    def __init__(self, config_key: _Optional[str] = ..., value: _Optional[str] = ..., updated_at: _Optional[str] = ..., description: _Optional[str] = ...) -> None: ...

class ListServiceConfigResponse(_message.Message):
    __slots__ = ("entries",)
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    entries: _containers.RepeatedCompositeFieldContainer[ServiceConfigEntry]
    def __init__(self, entries: _Optional[_Iterable[_Union[ServiceConfigEntry, _Mapping]]] = ...) -> None: ...

class GetServiceConfigRequest(_message.Message):
    __slots__ = ("config_key",)
    CONFIG_KEY_FIELD_NUMBER: _ClassVar[int]
    config_key: str
    def __init__(self, config_key: _Optional[str] = ...) -> None: ...

class PutServiceConfigRequest(_message.Message):
    __slots__ = ("config_key", "value", "description")
    CONFIG_KEY_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    config_key: str
    value: str
    description: str
    def __init__(self, config_key: _Optional[str] = ..., value: _Optional[str] = ..., description: _Optional[str] = ...) -> None: ...

class DeleteServiceConfigRequest(_message.Message):
    __slots__ = ("config_key",)
    CONFIG_KEY_FIELD_NUMBER: _ClassVar[int]
    config_key: str
    def __init__(self, config_key: _Optional[str] = ...) -> None: ...

class DeleteServiceConfigResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...
