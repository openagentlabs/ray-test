import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class PingRequest(_message.Message):
    __slots__ = ("client_name",)
    CLIENT_NAME_FIELD_NUMBER: _ClassVar[int]
    client_name: str
    def __init__(self, client_name: _Optional[str] = ...) -> None: ...

class PingReply(_message.Message):
    __slots__ = ("service_name", "version")
    SERVICE_NAME_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    service_name: str
    version: str
    def __init__(self, service_name: _Optional[str] = ..., version: _Optional[str] = ...) -> None: ...

class EchoRequest(_message.Message):
    __slots__ = ("message",)
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    message: str
    def __init__(self, message: _Optional[str] = ...) -> None: ...

class EchoReply(_message.Message):
    __slots__ = ("message",)
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    message: str
    def __init__(self, message: _Optional[str] = ...) -> None: ...

class RecordCountRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class RecordCountReply(_message.Message):
    __slots__ = ("total_records",)
    TOTAL_RECORDS_FIELD_NUMBER: _ClassVar[int]
    total_records: int
    def __init__(self, total_records: _Optional[int] = ...) -> None: ...

class EnsureInitialUserRequest(_message.Message):
    __slots__ = ("first_name", "last_name", "email", "password", "enabled", "notes", "timezone", "location")
    FIRST_NAME_FIELD_NUMBER: _ClassVar[int]
    LAST_NAME_FIELD_NUMBER: _ClassVar[int]
    EMAIL_FIELD_NUMBER: _ClassVar[int]
    PASSWORD_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    NOTES_FIELD_NUMBER: _ClassVar[int]
    TIMEZONE_FIELD_NUMBER: _ClassVar[int]
    LOCATION_FIELD_NUMBER: _ClassVar[int]
    first_name: str
    last_name: str
    email: str
    password: str
    enabled: bool
    notes: str
    timezone: str
    location: str
    def __init__(self, first_name: _Optional[str] = ..., last_name: _Optional[str] = ..., email: _Optional[str] = ..., password: _Optional[str] = ..., enabled: bool = ..., notes: _Optional[str] = ..., timezone: _Optional[str] = ..., location: _Optional[str] = ...) -> None: ...

class EnsureInitialUserReply(_message.Message):
    __slots__ = ("skipped", "created", "user", "login")
    SKIPPED_FIELD_NUMBER: _ClassVar[int]
    CREATED_FIELD_NUMBER: _ClassVar[int]
    USER_FIELD_NUMBER: _ClassVar[int]
    LOGIN_FIELD_NUMBER: _ClassVar[int]
    skipped: bool
    created: bool
    user: User
    login: Login
    def __init__(self, skipped: bool = ..., created: bool = ..., user: _Optional[_Union[User, _Mapping]] = ..., login: _Optional[_Union[Login, _Mapping]] = ...) -> None: ...

class ResetDatabaseRequest(_message.Message):
    __slots__ = ("username", "password")
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    PASSWORD_FIELD_NUMBER: _ClassVar[int]
    username: str
    password: str
    def __init__(self, username: _Optional[str] = ..., password: _Optional[str] = ...) -> None: ...

class ResetDatabaseReply(_message.Message):
    __slots__ = ("total_records_before_reset", "user", "login")
    TOTAL_RECORDS_BEFORE_RESET_FIELD_NUMBER: _ClassVar[int]
    USER_FIELD_NUMBER: _ClassVar[int]
    LOGIN_FIELD_NUMBER: _ClassVar[int]
    total_records_before_reset: int
    user: User
    login: Login
    def __init__(self, total_records_before_reset: _Optional[int] = ..., user: _Optional[_Union[User, _Mapping]] = ..., login: _Optional[_Union[Login, _Mapping]] = ...) -> None: ...

class GetUserByEmailRequest(_message.Message):
    __slots__ = ("email",)
    EMAIL_FIELD_NUMBER: _ClassVar[int]
    email: str
    def __init__(self, email: _Optional[str] = ...) -> None: ...

class GetUserDataRequest(_message.Message):
    __slots__ = ("id", "include_deleted")
    ID_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_DELETED_FIELD_NUMBER: _ClassVar[int]
    id: str
    include_deleted: bool
    def __init__(self, id: _Optional[str] = ..., include_deleted: bool = ...) -> None: ...

class GetUserDataReply(_message.Message):
    __slots__ = ("user_id", "username", "password", "login_id")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    PASSWORD_FIELD_NUMBER: _ClassVar[int]
    LOGIN_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    username: str
    password: str
    login_id: str
    def __init__(self, user_id: _Optional[str] = ..., username: _Optional[str] = ..., password: _Optional[str] = ..., login_id: _Optional[str] = ...) -> None: ...

class UserShort(_message.Message):
    __slots__ = ("id", "first_name", "last_name", "enabled", "account_id", "user_type_id", "created_at", "updated_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    FIRST_NAME_FIELD_NUMBER: _ClassVar[int]
    LAST_NAME_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    USER_TYPE_ID_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    first_name: str
    last_name: str
    enabled: bool
    account_id: str
    user_type_id: str
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., first_name: _Optional[str] = ..., last_name: _Optional[str] = ..., enabled: bool = ..., account_id: _Optional[str] = ..., user_type_id: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class User(_message.Message):
    __slots__ = ("id", "created_at", "updated_at", "deleted_at", "is_deleted", "enabled", "first_name", "last_name", "account_id", "notes", "timezone", "location", "skill_list_id", "user_type_id")
    ID_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    DELETED_AT_FIELD_NUMBER: _ClassVar[int]
    IS_DELETED_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    FIRST_NAME_FIELD_NUMBER: _ClassVar[int]
    LAST_NAME_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    NOTES_FIELD_NUMBER: _ClassVar[int]
    TIMEZONE_FIELD_NUMBER: _ClassVar[int]
    LOCATION_FIELD_NUMBER: _ClassVar[int]
    SKILL_LIST_ID_FIELD_NUMBER: _ClassVar[int]
    USER_TYPE_ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    deleted_at: _timestamp_pb2.Timestamp
    is_deleted: bool
    enabled: bool
    first_name: str
    last_name: str
    account_id: str
    notes: str
    timezone: str
    location: str
    skill_list_id: str
    user_type_id: str
    def __init__(self, id: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., deleted_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., is_deleted: bool = ..., enabled: bool = ..., first_name: _Optional[str] = ..., last_name: _Optional[str] = ..., account_id: _Optional[str] = ..., notes: _Optional[str] = ..., timezone: _Optional[str] = ..., location: _Optional[str] = ..., skill_list_id: _Optional[str] = ..., user_type_id: _Optional[str] = ...) -> None: ...

class UserType(_message.Message):
    __slots__ = ("id", "created_at", "updated_at", "deleted_at", "is_deleted", "enabled", "code", "display_name", "data_json")
    ID_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    DELETED_AT_FIELD_NUMBER: _ClassVar[int]
    IS_DELETED_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    DATA_JSON_FIELD_NUMBER: _ClassVar[int]
    id: str
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    deleted_at: _timestamp_pb2.Timestamp
    is_deleted: bool
    enabled: bool
    code: str
    display_name: str
    data_json: str
    def __init__(self, id: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., deleted_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., is_deleted: bool = ..., enabled: bool = ..., code: _Optional[str] = ..., display_name: _Optional[str] = ..., data_json: _Optional[str] = ...) -> None: ...

class SkillList(_message.Message):
    __slots__ = ("id", "created_at", "updated_at", "deleted_at", "is_deleted", "enabled", "name", "data_json")
    ID_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    DELETED_AT_FIELD_NUMBER: _ClassVar[int]
    IS_DELETED_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DATA_JSON_FIELD_NUMBER: _ClassVar[int]
    id: str
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    deleted_at: _timestamp_pb2.Timestamp
    is_deleted: bool
    enabled: bool
    name: str
    data_json: str
    def __init__(self, id: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., deleted_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., is_deleted: bool = ..., enabled: bool = ..., name: _Optional[str] = ..., data_json: _Optional[str] = ...) -> None: ...

class Skill(_message.Message):
    __slots__ = ("id", "created_at", "updated_at", "deleted_at", "is_deleted", "enabled", "code", "display_name", "data_json")
    ID_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    DELETED_AT_FIELD_NUMBER: _ClassVar[int]
    IS_DELETED_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    DATA_JSON_FIELD_NUMBER: _ClassVar[int]
    id: str
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    deleted_at: _timestamp_pb2.Timestamp
    is_deleted: bool
    enabled: bool
    code: str
    display_name: str
    data_json: str
    def __init__(self, id: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., deleted_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., is_deleted: bool = ..., enabled: bool = ..., code: _Optional[str] = ..., display_name: _Optional[str] = ..., data_json: _Optional[str] = ...) -> None: ...

class UserSkill(_message.Message):
    __slots__ = ("id", "user_id", "skill_id", "created_at", "updated_at", "deleted_at", "is_deleted")
    ID_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    SKILL_ID_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    DELETED_AT_FIELD_NUMBER: _ClassVar[int]
    IS_DELETED_FIELD_NUMBER: _ClassVar[int]
    id: str
    user_id: str
    skill_id: str
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    deleted_at: _timestamp_pb2.Timestamp
    is_deleted: bool
    def __init__(self, id: _Optional[str] = ..., user_id: _Optional[str] = ..., skill_id: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., deleted_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., is_deleted: bool = ...) -> None: ...

class LoginType(_message.Message):
    __slots__ = ("id", "created_at", "updated_at", "deleted_at", "is_deleted", "enabled", "code", "display_name", "data_json")
    ID_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    DELETED_AT_FIELD_NUMBER: _ClassVar[int]
    IS_DELETED_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    DATA_JSON_FIELD_NUMBER: _ClassVar[int]
    id: str
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    deleted_at: _timestamp_pb2.Timestamp
    is_deleted: bool
    enabled: bool
    code: str
    display_name: str
    data_json: str
    def __init__(self, id: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., deleted_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., is_deleted: bool = ..., enabled: bool = ..., code: _Optional[str] = ..., display_name: _Optional[str] = ..., data_json: _Optional[str] = ...) -> None: ...

class Login(_message.Message):
    __slots__ = ("id", "user_id", "login_type_id", "name", "description", "created_at", "updated_at", "deleted_at", "is_deleted", "enabled", "data_json", "password")
    ID_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    LOGIN_TYPE_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    DELETED_AT_FIELD_NUMBER: _ClassVar[int]
    IS_DELETED_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    DATA_JSON_FIELD_NUMBER: _ClassVar[int]
    PASSWORD_FIELD_NUMBER: _ClassVar[int]
    id: str
    user_id: str
    login_type_id: str
    name: str
    description: str
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    deleted_at: _timestamp_pb2.Timestamp
    is_deleted: bool
    enabled: bool
    data_json: str
    password: str
    def __init__(self, id: _Optional[str] = ..., user_id: _Optional[str] = ..., login_type_id: _Optional[str] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., deleted_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., is_deleted: bool = ..., enabled: bool = ..., data_json: _Optional[str] = ..., password: _Optional[str] = ...) -> None: ...

class LoginDetail(_message.Message):
    __slots__ = ("login", "login_type")
    LOGIN_FIELD_NUMBER: _ClassVar[int]
    LOGIN_TYPE_FIELD_NUMBER: _ClassVar[int]
    login: Login
    login_type: LoginType
    def __init__(self, login: _Optional[_Union[Login, _Mapping]] = ..., login_type: _Optional[_Union[LoginType, _Mapping]] = ...) -> None: ...

class UserLong(_message.Message):
    __slots__ = ("user", "user_type", "skill_list", "logins", "skills")
    USER_FIELD_NUMBER: _ClassVar[int]
    USER_TYPE_FIELD_NUMBER: _ClassVar[int]
    SKILL_LIST_FIELD_NUMBER: _ClassVar[int]
    LOGINS_FIELD_NUMBER: _ClassVar[int]
    SKILLS_FIELD_NUMBER: _ClassVar[int]
    user: User
    user_type: UserType
    skill_list: SkillList
    logins: _containers.RepeatedCompositeFieldContainer[LoginDetail]
    skills: _containers.RepeatedCompositeFieldContainer[Skill]
    def __init__(self, user: _Optional[_Union[User, _Mapping]] = ..., user_type: _Optional[_Union[UserType, _Mapping]] = ..., skill_list: _Optional[_Union[SkillList, _Mapping]] = ..., logins: _Optional[_Iterable[_Union[LoginDetail, _Mapping]]] = ..., skills: _Optional[_Iterable[_Union[Skill, _Mapping]]] = ...) -> None: ...

class CreateUserRequest(_message.Message):
    __slots__ = ("first_name", "last_name", "account_id", "notes", "timezone", "location", "skill_list_id", "user_type_id", "enabled", "skill_ids")
    FIRST_NAME_FIELD_NUMBER: _ClassVar[int]
    LAST_NAME_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    NOTES_FIELD_NUMBER: _ClassVar[int]
    TIMEZONE_FIELD_NUMBER: _ClassVar[int]
    LOCATION_FIELD_NUMBER: _ClassVar[int]
    SKILL_LIST_ID_FIELD_NUMBER: _ClassVar[int]
    USER_TYPE_ID_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    SKILL_IDS_FIELD_NUMBER: _ClassVar[int]
    first_name: str
    last_name: str
    account_id: str
    notes: str
    timezone: str
    location: str
    skill_list_id: str
    user_type_id: str
    enabled: bool
    skill_ids: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, first_name: _Optional[str] = ..., last_name: _Optional[str] = ..., account_id: _Optional[str] = ..., notes: _Optional[str] = ..., timezone: _Optional[str] = ..., location: _Optional[str] = ..., skill_list_id: _Optional[str] = ..., user_type_id: _Optional[str] = ..., enabled: bool = ..., skill_ids: _Optional[_Iterable[str]] = ...) -> None: ...

class GetUserRequest(_message.Message):
    __slots__ = ("id", "include_deleted")
    ID_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_DELETED_FIELD_NUMBER: _ClassVar[int]
    id: str
    include_deleted: bool
    def __init__(self, id: _Optional[str] = ..., include_deleted: bool = ...) -> None: ...

class UpdateUserRequest(_message.Message):
    __slots__ = ("id", "first_name", "last_name", "account_id", "notes", "timezone", "location", "skill_list_id", "user_type_id", "enabled")
    ID_FIELD_NUMBER: _ClassVar[int]
    FIRST_NAME_FIELD_NUMBER: _ClassVar[int]
    LAST_NAME_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    NOTES_FIELD_NUMBER: _ClassVar[int]
    TIMEZONE_FIELD_NUMBER: _ClassVar[int]
    LOCATION_FIELD_NUMBER: _ClassVar[int]
    SKILL_LIST_ID_FIELD_NUMBER: _ClassVar[int]
    USER_TYPE_ID_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    id: str
    first_name: str
    last_name: str
    account_id: str
    notes: str
    timezone: str
    location: str
    skill_list_id: str
    user_type_id: str
    enabled: bool
    def __init__(self, id: _Optional[str] = ..., first_name: _Optional[str] = ..., last_name: _Optional[str] = ..., account_id: _Optional[str] = ..., notes: _Optional[str] = ..., timezone: _Optional[str] = ..., location: _Optional[str] = ..., skill_list_id: _Optional[str] = ..., user_type_id: _Optional[str] = ..., enabled: bool = ...) -> None: ...

class SoftDeleteUserRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class ListUsersByAccountRequest(_message.Message):
    __slots__ = ("account_id", "include_deleted", "page_size", "page_token", "user_type_id", "enabled", "name_contains")
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_DELETED_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    USER_TYPE_ID_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    NAME_CONTAINS_FIELD_NUMBER: _ClassVar[int]
    account_id: str
    include_deleted: bool
    page_size: int
    page_token: str
    user_type_id: str
    enabled: bool
    name_contains: str
    def __init__(self, account_id: _Optional[str] = ..., include_deleted: bool = ..., page_size: _Optional[int] = ..., page_token: _Optional[str] = ..., user_type_id: _Optional[str] = ..., enabled: bool = ..., name_contains: _Optional[str] = ...) -> None: ...

class ListUsersByAccountReply(_message.Message):
    __slots__ = ("users", "next_page_token")
    USERS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    users: _containers.RepeatedCompositeFieldContainer[User]
    next_page_token: str
    def __init__(self, users: _Optional[_Iterable[_Union[User, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class GetUserTypeStatsRequest(_message.Message):
    __slots__ = ("account_id", "include_deleted")
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_DELETED_FIELD_NUMBER: _ClassVar[int]
    account_id: str
    include_deleted: bool
    def __init__(self, account_id: _Optional[str] = ..., include_deleted: bool = ...) -> None: ...

class UserTypeStat(_message.Message):
    __slots__ = ("type_name", "count")
    TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
    COUNT_FIELD_NUMBER: _ClassVar[int]
    type_name: str
    count: int
    def __init__(self, type_name: _Optional[str] = ..., count: _Optional[int] = ...) -> None: ...

class GetUserTypeStatsReply(_message.Message):
    __slots__ = ("entries",)
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    entries: _containers.RepeatedCompositeFieldContainer[UserTypeStat]
    def __init__(self, entries: _Optional[_Iterable[_Union[UserTypeStat, _Mapping]]] = ...) -> None: ...

class CreateUserTypeRequest(_message.Message):
    __slots__ = ("code", "display_name", "data_json", "enabled")
    CODE_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    DATA_JSON_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    code: str
    display_name: str
    data_json: str
    enabled: bool
    def __init__(self, code: _Optional[str] = ..., display_name: _Optional[str] = ..., data_json: _Optional[str] = ..., enabled: bool = ...) -> None: ...

class GetUserTypeRequest(_message.Message):
    __slots__ = ("id", "include_deleted")
    ID_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_DELETED_FIELD_NUMBER: _ClassVar[int]
    id: str
    include_deleted: bool
    def __init__(self, id: _Optional[str] = ..., include_deleted: bool = ...) -> None: ...

class UpdateUserTypeRequest(_message.Message):
    __slots__ = ("id", "code", "display_name", "data_json", "enabled")
    ID_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    DATA_JSON_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    id: str
    code: str
    display_name: str
    data_json: str
    enabled: bool
    def __init__(self, id: _Optional[str] = ..., code: _Optional[str] = ..., display_name: _Optional[str] = ..., data_json: _Optional[str] = ..., enabled: bool = ...) -> None: ...

class SoftDeleteUserTypeRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class ListUserTypesRequest(_message.Message):
    __slots__ = ("include_deleted", "page_size", "page_token")
    INCLUDE_DELETED_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    include_deleted: bool
    page_size: int
    page_token: str
    def __init__(self, include_deleted: bool = ..., page_size: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListUserTypesReply(_message.Message):
    __slots__ = ("items", "next_page_token")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[UserType]
    next_page_token: str
    def __init__(self, items: _Optional[_Iterable[_Union[UserType, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class CreateLoginTypeRequest(_message.Message):
    __slots__ = ("code", "display_name", "data_json", "enabled")
    CODE_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    DATA_JSON_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    code: str
    display_name: str
    data_json: str
    enabled: bool
    def __init__(self, code: _Optional[str] = ..., display_name: _Optional[str] = ..., data_json: _Optional[str] = ..., enabled: bool = ...) -> None: ...

class GetLoginTypeRequest(_message.Message):
    __slots__ = ("id", "include_deleted")
    ID_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_DELETED_FIELD_NUMBER: _ClassVar[int]
    id: str
    include_deleted: bool
    def __init__(self, id: _Optional[str] = ..., include_deleted: bool = ...) -> None: ...

class UpdateLoginTypeRequest(_message.Message):
    __slots__ = ("id", "code", "display_name", "data_json", "enabled")
    ID_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    DATA_JSON_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    id: str
    code: str
    display_name: str
    data_json: str
    enabled: bool
    def __init__(self, id: _Optional[str] = ..., code: _Optional[str] = ..., display_name: _Optional[str] = ..., data_json: _Optional[str] = ..., enabled: bool = ...) -> None: ...

class SoftDeleteLoginTypeRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class ListLoginTypesRequest(_message.Message):
    __slots__ = ("include_deleted", "page_size", "page_token")
    INCLUDE_DELETED_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    include_deleted: bool
    page_size: int
    page_token: str
    def __init__(self, include_deleted: bool = ..., page_size: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListLoginTypesReply(_message.Message):
    __slots__ = ("items", "next_page_token")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[LoginType]
    next_page_token: str
    def __init__(self, items: _Optional[_Iterable[_Union[LoginType, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class CreateSkillListRequest(_message.Message):
    __slots__ = ("name", "data_json", "enabled")
    NAME_FIELD_NUMBER: _ClassVar[int]
    DATA_JSON_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    name: str
    data_json: str
    enabled: bool
    def __init__(self, name: _Optional[str] = ..., data_json: _Optional[str] = ..., enabled: bool = ...) -> None: ...

class GetSkillListRequest(_message.Message):
    __slots__ = ("id", "include_deleted")
    ID_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_DELETED_FIELD_NUMBER: _ClassVar[int]
    id: str
    include_deleted: bool
    def __init__(self, id: _Optional[str] = ..., include_deleted: bool = ...) -> None: ...

class UpdateSkillListRequest(_message.Message):
    __slots__ = ("id", "name", "data_json", "enabled")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DATA_JSON_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    data_json: str
    enabled: bool
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., data_json: _Optional[str] = ..., enabled: bool = ...) -> None: ...

class SoftDeleteSkillListRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class ListSkillsRequest(_message.Message):
    __slots__ = ("include_deleted", "page_size", "page_token")
    INCLUDE_DELETED_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    include_deleted: bool
    page_size: int
    page_token: str
    def __init__(self, include_deleted: bool = ..., page_size: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListSkillsReply(_message.Message):
    __slots__ = ("items", "next_page_token")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[Skill]
    next_page_token: str
    def __init__(self, items: _Optional[_Iterable[_Union[Skill, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class CreateSkillRequest(_message.Message):
    __slots__ = ("code", "display_name", "data_json", "enabled")
    CODE_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    DATA_JSON_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    code: str
    display_name: str
    data_json: str
    enabled: bool
    def __init__(self, code: _Optional[str] = ..., display_name: _Optional[str] = ..., data_json: _Optional[str] = ..., enabled: bool = ...) -> None: ...

class GetSkillRequest(_message.Message):
    __slots__ = ("id", "include_deleted")
    ID_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_DELETED_FIELD_NUMBER: _ClassVar[int]
    id: str
    include_deleted: bool
    def __init__(self, id: _Optional[str] = ..., include_deleted: bool = ...) -> None: ...

class UpdateSkillRequest(_message.Message):
    __slots__ = ("id", "code", "display_name", "data_json", "enabled")
    ID_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    DATA_JSON_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    id: str
    code: str
    display_name: str
    data_json: str
    enabled: bool
    def __init__(self, id: _Optional[str] = ..., code: _Optional[str] = ..., display_name: _Optional[str] = ..., data_json: _Optional[str] = ..., enabled: bool = ...) -> None: ...

class SoftDeleteSkillRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class ListUserSkillsRequest(_message.Message):
    __slots__ = ("user_id", "include_deleted", "page_size", "page_token")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_DELETED_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    include_deleted: bool
    page_size: int
    page_token: str
    def __init__(self, user_id: _Optional[str] = ..., include_deleted: bool = ..., page_size: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListUserSkillsReply(_message.Message):
    __slots__ = ("items", "next_page_token")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[UserSkill]
    next_page_token: str
    def __init__(self, items: _Optional[_Iterable[_Union[UserSkill, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class CreateUserSkillRequest(_message.Message):
    __slots__ = ("user_id", "skill_id")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    SKILL_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    skill_id: str
    def __init__(self, user_id: _Optional[str] = ..., skill_id: _Optional[str] = ...) -> None: ...

class SoftDeleteUserSkillRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class ReplaceUserSkillsRequest(_message.Message):
    __slots__ = ("user_id", "skill_ids")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    SKILL_IDS_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    skill_ids: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, user_id: _Optional[str] = ..., skill_ids: _Optional[_Iterable[str]] = ...) -> None: ...

class ReplaceUserSkillsReply(_message.Message):
    __slots__ = ("applied_count",)
    APPLIED_COUNT_FIELD_NUMBER: _ClassVar[int]
    applied_count: int
    def __init__(self, applied_count: _Optional[int] = ...) -> None: ...

class CreateLoginRequest(_message.Message):
    __slots__ = ("user_id", "login_type_id", "name", "description", "data_json", "enabled", "password")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    LOGIN_TYPE_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    DATA_JSON_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    PASSWORD_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    login_type_id: str
    name: str
    description: str
    data_json: str
    enabled: bool
    password: str
    def __init__(self, user_id: _Optional[str] = ..., login_type_id: _Optional[str] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., data_json: _Optional[str] = ..., enabled: bool = ..., password: _Optional[str] = ...) -> None: ...

class GetLoginRequest(_message.Message):
    __slots__ = ("id", "include_deleted")
    ID_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_DELETED_FIELD_NUMBER: _ClassVar[int]
    id: str
    include_deleted: bool
    def __init__(self, id: _Optional[str] = ..., include_deleted: bool = ...) -> None: ...

class UpdateLoginRequest(_message.Message):
    __slots__ = ("id", "login_type_id", "name", "description", "data_json", "enabled", "password")
    ID_FIELD_NUMBER: _ClassVar[int]
    LOGIN_TYPE_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    DATA_JSON_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    PASSWORD_FIELD_NUMBER: _ClassVar[int]
    id: str
    login_type_id: str
    name: str
    description: str
    data_json: str
    enabled: bool
    password: str
    def __init__(self, id: _Optional[str] = ..., login_type_id: _Optional[str] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., data_json: _Optional[str] = ..., enabled: bool = ..., password: _Optional[str] = ...) -> None: ...

class SoftDeleteLoginRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class ListLoginsByUserIdRequest(_message.Message):
    __slots__ = ("user_id", "include_deleted", "page_size", "page_token")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_DELETED_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    include_deleted: bool
    page_size: int
    page_token: str
    def __init__(self, user_id: _Optional[str] = ..., include_deleted: bool = ..., page_size: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListLoginsByUserIdReply(_message.Message):
    __slots__ = ("items", "next_page_token")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[LoginDetail]
    next_page_token: str
    def __init__(self, items: _Optional[_Iterable[_Union[LoginDetail, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class Session(_message.Message):
    __slots__ = ("id", "user_id", "login_id", "created_at", "expires_at", "deleted_at", "is_revoked", "first_name", "last_name", "email", "user_type_id", "user_type_display_name", "user_auth_context")
    ID_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    LOGIN_ID_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    DELETED_AT_FIELD_NUMBER: _ClassVar[int]
    IS_REVOKED_FIELD_NUMBER: _ClassVar[int]
    FIRST_NAME_FIELD_NUMBER: _ClassVar[int]
    LAST_NAME_FIELD_NUMBER: _ClassVar[int]
    EMAIL_FIELD_NUMBER: _ClassVar[int]
    USER_TYPE_ID_FIELD_NUMBER: _ClassVar[int]
    USER_TYPE_DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    USER_AUTH_CONTEXT_FIELD_NUMBER: _ClassVar[int]
    id: str
    user_id: str
    login_id: str
    created_at: _timestamp_pb2.Timestamp
    expires_at: _timestamp_pb2.Timestamp
    deleted_at: _timestamp_pb2.Timestamp
    is_revoked: bool
    first_name: str
    last_name: str
    email: str
    user_type_id: str
    user_type_display_name: str
    user_auth_context: UserAuthContext
    def __init__(self, id: _Optional[str] = ..., user_id: _Optional[str] = ..., login_id: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., deleted_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., is_revoked: bool = ..., first_name: _Optional[str] = ..., last_name: _Optional[str] = ..., email: _Optional[str] = ..., user_type_id: _Optional[str] = ..., user_type_display_name: _Optional[str] = ..., user_auth_context: _Optional[_Union[UserAuthContext, _Mapping]] = ...) -> None: ...

class UserAuthContext(_message.Message):
    __slots__ = ("user_id", "role_codes", "permission_grants", "auth_json")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    ROLE_CODES_FIELD_NUMBER: _ClassVar[int]
    PERMISSION_GRANTS_FIELD_NUMBER: _ClassVar[int]
    AUTH_JSON_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    role_codes: _containers.RepeatedScalarFieldContainer[str]
    permission_grants: _containers.RepeatedCompositeFieldContainer[PermissionGrant]
    auth_json: str
    def __init__(self, user_id: _Optional[str] = ..., role_codes: _Optional[_Iterable[str]] = ..., permission_grants: _Optional[_Iterable[_Union[PermissionGrant, _Mapping]]] = ..., auth_json: _Optional[str] = ...) -> None: ...

class PermissionGrant(_message.Message):
    __slots__ = ("permission_code", "role_code")
    PERMISSION_CODE_FIELD_NUMBER: _ClassVar[int]
    ROLE_CODE_FIELD_NUMBER: _ClassVar[int]
    permission_code: str
    role_code: str
    def __init__(self, permission_code: _Optional[str] = ..., role_code: _Optional[str] = ...) -> None: ...

class SignInCheckRequest(_message.Message):
    __slots__ = ("username", "password")
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    PASSWORD_FIELD_NUMBER: _ClassVar[int]
    username: str
    password: str
    def __init__(self, username: _Optional[str] = ..., password: _Optional[str] = ...) -> None: ...

class SignInCheckReply(_message.Message):
    __slots__ = ("user_id", "login_id")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    LOGIN_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    login_id: str
    def __init__(self, user_id: _Optional[str] = ..., login_id: _Optional[str] = ...) -> None: ...

class SignInRequest(_message.Message):
    __slots__ = ("username", "password")
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    PASSWORD_FIELD_NUMBER: _ClassVar[int]
    username: str
    password: str
    def __init__(self, username: _Optional[str] = ..., password: _Optional[str] = ...) -> None: ...

class SignOutRequest(_message.Message):
    __slots__ = ("session_id",)
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    def __init__(self, session_id: _Optional[str] = ...) -> None: ...

class SignOutReply(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class Invite(_message.Message):
    __slots__ = ("id", "created_at", "updated_at", "deleted_at", "is_deleted", "code", "expires_at", "redeemed", "account_id", "user_type_id", "login_type_id", "recipient_email")
    ID_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    DELETED_AT_FIELD_NUMBER: _ClassVar[int]
    IS_DELETED_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    REDEEMED_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    USER_TYPE_ID_FIELD_NUMBER: _ClassVar[int]
    LOGIN_TYPE_ID_FIELD_NUMBER: _ClassVar[int]
    RECIPIENT_EMAIL_FIELD_NUMBER: _ClassVar[int]
    id: str
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    deleted_at: _timestamp_pb2.Timestamp
    is_deleted: bool
    code: str
    expires_at: _timestamp_pb2.Timestamp
    redeemed: bool
    account_id: str
    user_type_id: str
    login_type_id: str
    recipient_email: str
    def __init__(self, id: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., deleted_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., is_deleted: bool = ..., code: _Optional[str] = ..., expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., redeemed: bool = ..., account_id: _Optional[str] = ..., user_type_id: _Optional[str] = ..., login_type_id: _Optional[str] = ..., recipient_email: _Optional[str] = ...) -> None: ...

class GenerateInviteRequest(_message.Message):
    __slots__ = ("account_id", "user_type_id", "login_type_id", "ttl_hours", "recipient_email")
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    USER_TYPE_ID_FIELD_NUMBER: _ClassVar[int]
    LOGIN_TYPE_ID_FIELD_NUMBER: _ClassVar[int]
    TTL_HOURS_FIELD_NUMBER: _ClassVar[int]
    RECIPIENT_EMAIL_FIELD_NUMBER: _ClassVar[int]
    account_id: str
    user_type_id: str
    login_type_id: str
    ttl_hours: int
    recipient_email: str
    def __init__(self, account_id: _Optional[str] = ..., user_type_id: _Optional[str] = ..., login_type_id: _Optional[str] = ..., ttl_hours: _Optional[int] = ..., recipient_email: _Optional[str] = ...) -> None: ...

class ListInvitesRequest(_message.Message):
    __slots__ = ("include_deleted", "page_size", "page_token")
    INCLUDE_DELETED_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    include_deleted: bool
    page_size: int
    page_token: str
    def __init__(self, include_deleted: bool = ..., page_size: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListInvitesReply(_message.Message):
    __slots__ = ("items", "next_page_token")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[Invite]
    next_page_token: str
    def __init__(self, items: _Optional[_Iterable[_Union[Invite, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class SoftDeleteInviteRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class RedeemInviteRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class SignUpUserRequest(_message.Message):
    __slots__ = ("email", "first_name", "last_name", "password", "password_confirm", "invite_code")
    EMAIL_FIELD_NUMBER: _ClassVar[int]
    FIRST_NAME_FIELD_NUMBER: _ClassVar[int]
    LAST_NAME_FIELD_NUMBER: _ClassVar[int]
    PASSWORD_FIELD_NUMBER: _ClassVar[int]
    PASSWORD_CONFIRM_FIELD_NUMBER: _ClassVar[int]
    INVITE_CODE_FIELD_NUMBER: _ClassVar[int]
    email: str
    first_name: str
    last_name: str
    password: str
    password_confirm: str
    invite_code: str
    def __init__(self, email: _Optional[str] = ..., first_name: _Optional[str] = ..., last_name: _Optional[str] = ..., password: _Optional[str] = ..., password_confirm: _Optional[str] = ..., invite_code: _Optional[str] = ...) -> None: ...

class SignUpUserReply(_message.Message):
    __slots__ = ("user", "login")
    USER_FIELD_NUMBER: _ClassVar[int]
    LOGIN_FIELD_NUMBER: _ClassVar[int]
    user: User
    login: Login
    def __init__(self, user: _Optional[_Union[User, _Mapping]] = ..., login: _Optional[_Union[Login, _Mapping]] = ...) -> None: ...

class Role(_message.Message):
    __slots__ = ("id", "created_at", "updated_at", "deleted_at", "is_deleted", "enabled", "code", "display_name", "data_json")
    ID_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    DELETED_AT_FIELD_NUMBER: _ClassVar[int]
    IS_DELETED_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    DATA_JSON_FIELD_NUMBER: _ClassVar[int]
    id: str
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    deleted_at: _timestamp_pb2.Timestamp
    is_deleted: bool
    enabled: bool
    code: str
    display_name: str
    data_json: str
    def __init__(self, id: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., deleted_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., is_deleted: bool = ..., enabled: bool = ..., code: _Optional[str] = ..., display_name: _Optional[str] = ..., data_json: _Optional[str] = ...) -> None: ...

class Permission(_message.Message):
    __slots__ = ("id", "created_at", "updated_at", "deleted_at", "is_deleted", "enabled", "code", "display_name", "data_json")
    ID_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    DELETED_AT_FIELD_NUMBER: _ClassVar[int]
    IS_DELETED_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    DATA_JSON_FIELD_NUMBER: _ClassVar[int]
    id: str
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    deleted_at: _timestamp_pb2.Timestamp
    is_deleted: bool
    enabled: bool
    code: str
    display_name: str
    data_json: str
    def __init__(self, id: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., deleted_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., is_deleted: bool = ..., enabled: bool = ..., code: _Optional[str] = ..., display_name: _Optional[str] = ..., data_json: _Optional[str] = ...) -> None: ...

class RolePermission(_message.Message):
    __slots__ = ("role_id", "permission_id", "role_code", "permission_code", "created_at", "updated_at")
    ROLE_ID_FIELD_NUMBER: _ClassVar[int]
    PERMISSION_ID_FIELD_NUMBER: _ClassVar[int]
    ROLE_CODE_FIELD_NUMBER: _ClassVar[int]
    PERMISSION_CODE_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    role_id: str
    permission_id: str
    role_code: str
    permission_code: str
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    def __init__(self, role_id: _Optional[str] = ..., permission_id: _Optional[str] = ..., role_code: _Optional[str] = ..., permission_code: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class UserRoleAssignment(_message.Message):
    __slots__ = ("user_id", "role_id", "role_code", "created_at", "updated_at")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    ROLE_ID_FIELD_NUMBER: _ClassVar[int]
    ROLE_CODE_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    role_id: str
    role_code: str
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    def __init__(self, user_id: _Optional[str] = ..., role_id: _Optional[str] = ..., role_code: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class ServicePermission(_message.Message):
    __slots__ = ("service_code", "permission_code", "created_at", "updated_at")
    SERVICE_CODE_FIELD_NUMBER: _ClassVar[int]
    PERMISSION_CODE_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    service_code: str
    permission_code: str
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    def __init__(self, service_code: _Optional[str] = ..., permission_code: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class ListRolesRequest(_message.Message):
    __slots__ = ("include_deleted", "page_size", "page_token")
    INCLUDE_DELETED_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    include_deleted: bool
    page_size: int
    page_token: str
    def __init__(self, include_deleted: bool = ..., page_size: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListRolesReply(_message.Message):
    __slots__ = ("items", "next_page_token")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[Role]
    next_page_token: str
    def __init__(self, items: _Optional[_Iterable[_Union[Role, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class CreateRoleRequest(_message.Message):
    __slots__ = ("code", "display_name", "data_json", "enabled")
    CODE_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    DATA_JSON_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    code: str
    display_name: str
    data_json: str
    enabled: bool
    def __init__(self, code: _Optional[str] = ..., display_name: _Optional[str] = ..., data_json: _Optional[str] = ..., enabled: bool = ...) -> None: ...

class ListPermissionsRequest(_message.Message):
    __slots__ = ("include_deleted", "page_size", "page_token")
    INCLUDE_DELETED_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    include_deleted: bool
    page_size: int
    page_token: str
    def __init__(self, include_deleted: bool = ..., page_size: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListPermissionsReply(_message.Message):
    __slots__ = ("items", "next_page_token")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[Permission]
    next_page_token: str
    def __init__(self, items: _Optional[_Iterable[_Union[Permission, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class CreatePermissionRequest(_message.Message):
    __slots__ = ("code", "display_name", "data_json", "enabled")
    CODE_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    DATA_JSON_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    code: str
    display_name: str
    data_json: str
    enabled: bool
    def __init__(self, code: _Optional[str] = ..., display_name: _Optional[str] = ..., data_json: _Optional[str] = ..., enabled: bool = ...) -> None: ...

class AttachPermissionToRoleRequest(_message.Message):
    __slots__ = ("role_id", "permission_id")
    ROLE_ID_FIELD_NUMBER: _ClassVar[int]
    PERMISSION_ID_FIELD_NUMBER: _ClassVar[int]
    role_id: str
    permission_id: str
    def __init__(self, role_id: _Optional[str] = ..., permission_id: _Optional[str] = ...) -> None: ...

class AssignRoleToUserRequest(_message.Message):
    __slots__ = ("user_id", "role_id")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    ROLE_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    role_id: str
    def __init__(self, user_id: _Optional[str] = ..., role_id: _Optional[str] = ...) -> None: ...

class RevokeRoleFromUserRequest(_message.Message):
    __slots__ = ("user_id", "role_id")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    ROLE_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    role_id: str
    def __init__(self, user_id: _Optional[str] = ..., role_id: _Optional[str] = ...) -> None: ...

class RevokeRoleFromUserReply(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListUserRolesRequest(_message.Message):
    __slots__ = ("user_id",)
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    def __init__(self, user_id: _Optional[str] = ...) -> None: ...

class ListUserRolesReply(_message.Message):
    __slots__ = ("items",)
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[UserRoleAssignment]
    def __init__(self, items: _Optional[_Iterable[_Union[UserRoleAssignment, _Mapping]]] = ...) -> None: ...

class CheckUserAuthAndPermissionsRequest(_message.Message):
    __slots__ = ("user_id", "user_auth_context", "permission_codes", "require_all")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    USER_AUTH_CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PERMISSION_CODES_FIELD_NUMBER: _ClassVar[int]
    REQUIRE_ALL_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    user_auth_context: UserAuthContext
    permission_codes: _containers.RepeatedScalarFieldContainer[str]
    require_all: bool
    def __init__(self, user_id: _Optional[str] = ..., user_auth_context: _Optional[_Union[UserAuthContext, _Mapping]] = ..., permission_codes: _Optional[_Iterable[str]] = ..., require_all: bool = ...) -> None: ...

class CheckUserAuthAndPermissionsReply(_message.Message):
    __slots__ = ("user_auth_context", "authorized", "missing_permission_codes")
    USER_AUTH_CONTEXT_FIELD_NUMBER: _ClassVar[int]
    AUTHORIZED_FIELD_NUMBER: _ClassVar[int]
    MISSING_PERMISSION_CODES_FIELD_NUMBER: _ClassVar[int]
    user_auth_context: UserAuthContext
    authorized: bool
    missing_permission_codes: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, user_auth_context: _Optional[_Union[UserAuthContext, _Mapping]] = ..., authorized: bool = ..., missing_permission_codes: _Optional[_Iterable[str]] = ...) -> None: ...

class ListServicePermissionsRequest(_message.Message):
    __slots__ = ("service_code",)
    SERVICE_CODE_FIELD_NUMBER: _ClassVar[int]
    service_code: str
    def __init__(self, service_code: _Optional[str] = ...) -> None: ...

class ListServicePermissionsReply(_message.Message):
    __slots__ = ("items",)
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[ServicePermission]
    def __init__(self, items: _Optional[_Iterable[_Union[ServicePermission, _Mapping]]] = ...) -> None: ...

class RegisterServicePermissionRequest(_message.Message):
    __slots__ = ("service_code", "permission_code")
    SERVICE_CODE_FIELD_NUMBER: _ClassVar[int]
    PERMISSION_CODE_FIELD_NUMBER: _ClassVar[int]
    service_code: str
    permission_code: str
    def __init__(self, service_code: _Optional[str] = ..., permission_code: _Optional[str] = ...) -> None: ...
