"""Unit tests for HelloWorldAction metadata and invoke."""

from __future__ import annotations

from returns.result import Success

from tf_tool.actions.helloworld import HelloWorldAction


def test_helloworld_action_metadata() -> None:
    action = HelloWorldAction()
    assert action.id == "a3f2c8e1-9b4d-4f6a-bc12-8e7d5f3a1c20"
    assert action.name == "helloworld"
    assert action.description == "Demo greeting (smoke test)."
    assert action.version == "0.1.0"
    assert action.FLAG_SHORT == "-w"
    assert action.FLAG_LONG == "--helloworld"


def test_helloworld_action_invoke() -> None:
    action = HelloWorldAction()
    result = action.invoke(name="UV")
    assert isinstance(result, Success)
    assert result.unwrap() == "Hello, UV!"
