import pytest
from typing import Any, List
from justpipe import Pipe, EventType


async def process_data(data: str) -> str:
    return data.upper()


@pytest.mark.asyncio
async def test_etl_pipeline_simulation() -> None:
    """Simulate a simple ETL pipeline."""

    class AppState:
        def __init__(self) -> None:
            self.raw_data: List[str] = []
            self.processed_data: List[str] = []
            self.db_committed = False

    app: AppState = AppState()
    pipe: Pipe[AppState, Any] = Pipe()

    @pipe.step("extract", to="transform")
    async def extract(state: AppState) -> None:
        state.raw_data = ["a", "b", "c"]

    @pipe.step("transform", to="load")
    async def transform(state: AppState) -> None:
        for item in state.raw_data:
            processed = await process_data(item)
            state.processed_data.append(processed)

    @pipe.step("load")
    async def load(state: AppState) -> None:
        state.db_committed = True

    events = []
    async for event in pipe.run(app):
        events.append(event)

    assert app.db_committed
    assert app.processed_data == ["A", "B", "C"]

    stages = [e.stage for e in events if e.type == EventType.STEP_END]
    # Order might vary in async graph, but here it's linear
    assert stages == ["extract", "transform", "load"]
