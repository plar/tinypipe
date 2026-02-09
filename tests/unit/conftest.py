import pytest
from tests.unit.fakes import FakeOrchestrator


@pytest.fixture
def fake_orchestrator() -> FakeOrchestrator:
    return FakeOrchestrator()
