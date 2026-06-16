"""Tests for the AWS object model."""

from __future__ import annotations

from returns.result import Failure, Success

from jp_tool.aws import Aws, AwsAccount, ConnectionInfo, ConnectionInfoBase
from jp_tool.core.errors import ErrorCodes


def test_aws_account_new_accepts_valid_id() -> None:
    result = AwsAccount.new("017868795096")

    assert isinstance(result, Success)
    account = result.unwrap()
    assert account.account_id == "017868795096"


def test_aws_account_new_rejects_empty_id() -> None:
    result = AwsAccount.new("")

    assert isinstance(result, Failure)
    error = result.failure()
    assert error.code == ErrorCodes.VALIDATION
    assert "required" in error.message.lower()


def test_aws_account_new_rejects_invalid_format() -> None:
    result = AwsAccount.new("12345")

    assert isinstance(result, Failure)
    error = result.failure()
    assert error.code == ErrorCodes.VALIDATION
    assert "invalid format" in error.message.lower()


def test_aws_account_id_is_read_only() -> None:
    account = AwsAccount.new("017868795096").unwrap()

    assert account.account_id == "017868795096"
    assert isinstance(type(account).account_id, property)


def test_aws_new_without_account_id() -> None:
    result = Aws.new()

    assert isinstance(result, Success)
    aws = result.unwrap()
    assert len(aws.accounts) == 0


def test_aws_new_registers_initial_account() -> None:
    result = Aws.new(account_id="017868795096")

    assert isinstance(result, Success)
    aws = result.unwrap()
    assert "017868795096" in aws.accounts
    assert aws.accounts["017868795096"].account_id == "017868795096"


def test_aws_new_propagates_invalid_account_id() -> None:
    result = Aws.new(account_id="not-valid")

    assert isinstance(result, Failure)
    assert result.failure().code == ErrorCodes.VALIDATION


def test_aws_register_account_skips_existing_id() -> None:
    aws = Aws.new(account_id="017868795096").unwrap()
    first = aws.accounts["017868795096"]

    register_result = aws._register_account("017868795096")

    assert isinstance(register_result, Success)
    assert aws.accounts["017868795096"] is first


def test_aws_register_account_skips_existing_id_with_whitespace() -> None:
    aws = Aws.new(account_id="017868795096").unwrap()
    first = aws.accounts["017868795096"]

    register_result = aws._register_account(" 017868795096 ")

    assert isinstance(register_result, Success)
    assert aws.accounts["017868795096"] is first
    assert len(aws.accounts) == 1


def test_connection_info_new_accepts_valid_values() -> None:
    result = ConnectionInfo.new("kt-acc", "us-east-1")

    assert isinstance(result, Success)
    connection = result.unwrap()
    assert connection.profile == "kt-acc"
    assert connection.region == "us-east-1"
    assert connection.connection_key == "kt-acc@us-east-1"
    assert isinstance(connection, ConnectionInfoBase)


def test_connection_info_new_rejects_missing_profile() -> None:
    result = ConnectionInfo.new("", "us-east-1")

    assert isinstance(result, Failure)
    assert result.failure().code == ErrorCodes.VALIDATION


def test_connection_info_new_rejects_invalid_region() -> None:
    result = ConnectionInfo.new("kt-acc", "INVALID REGION")

    assert isinstance(result, Failure)
    assert result.failure().code == ErrorCodes.VALIDATION


def test_connection_info_properties_are_read_only() -> None:
    connection = ConnectionInfo.new("kt-acc", "us-east-1").unwrap()

    assert isinstance(type(connection).profile, property)
    assert isinstance(type(connection).region, property)


def test_aws_new_registers_initial_connection() -> None:
    result = Aws.new(profile="kt-acc", region="us-east-1")

    assert isinstance(result, Success)
    aws = result.unwrap()
    assert "kt-acc@us-east-1" in aws.connections
    assert aws.connections["kt-acc@us-east-1"].profile == "kt-acc"


def test_aws_new_rejects_partial_connection_args() -> None:
    profile_only = Aws.new(profile="kt-acc")
    region_only = Aws.new(region="us-east-1")

    assert isinstance(profile_only, Failure)
    assert isinstance(region_only, Failure)


def test_aws_new_propagates_invalid_connection() -> None:
    result = Aws.new(profile="kt-acc", region="")

    assert isinstance(result, Failure)
    assert result.failure().code == ErrorCodes.VALIDATION


def test_aws_register_connection_skips_existing_key() -> None:
    aws = Aws.new(profile="kt-acc", region="us-east-1").unwrap()
    first = aws.connections["kt-acc@us-east-1"]

    register_result = aws._register_connection("kt-acc", "us-east-1")

    assert isinstance(register_result, Success)
    assert aws.connections["kt-acc@us-east-1"] is first
    assert len(aws.connections) == 1


def test_aws_new_registers_account_and_connection_together() -> None:
    result = Aws.new(
        account_id="017868795096",
        profile="kt-acc",
        region="us-east-1",
    )

    assert isinstance(result, Success)
    aws = result.unwrap()
    assert len(aws.accounts) == 1
    assert len(aws.connections) == 1
