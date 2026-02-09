import pytest
from justpipe.types import DefinitionError
from justpipe._internal.definition.registry_validator import _RegistryValidator


def test_validate_linear_to_valid() -> None:
    validator = _RegistryValidator()
    # Should not raise
    validator.validate_linear_to("step1", "step2")
    validator.validate_linear_to("step1", ["step2", "step3"])
    validator.validate_linear_to("step1", None)


def test_validate_linear_to_invalid_dict() -> None:
    validator = _RegistryValidator()
    with pytest.raises(DefinitionError, match="uses a dictionary for 'to='"):
        validator.validate_linear_to("step1", {"a": "b"})


def test_validate_linear_to_invalid_type() -> None:
    validator = _RegistryValidator()
    with pytest.raises(DefinitionError, match="has invalid 'to=' type"):
        validator.validate_linear_to("step1", 123)


def test_validate_routing_target_valid() -> None:
    validator = _RegistryValidator()
    # Should not raise
    validator.validate_routing_target("target", "owner")
    validator.validate_routing_target(["t1", "t2"], "owner")


def test_validate_routing_target_invalid() -> None:
    validator = _RegistryValidator()
    with pytest.raises(DefinitionError, match="cannot route to itself"):
        validator.validate_routing_target("self", "self")

    with pytest.raises(DefinitionError, match="cannot route to itself"):
        validator.validate_routing_target(["a", "self"], "self")


def test_validate_switch_routes_missing_target() -> None:
    validator = _RegistryValidator()
    # We need a way to mock the available steps
    available_steps = ["step1", "step2"]
    validation_ctx = {"switch_name": "router", "targets": ["step1", "nonexistent"]}

    with pytest.raises(DefinitionError, match="routes to undefined step 'nonexistent'"):
        validator.validate_switch_routes(validation_ctx, available_steps)
