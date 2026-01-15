import pytest
from tinypipe import Pipe, EventType


@pytest.mark.asyncio
async def test_chatbot_acceptance(state):
    # The "Chatbot" Acceptance Test
    app = Pipe()
    count = 0

    @app.step("start", to=["wiki", "news"])
    async def start():
        pass

    @app.step("wiki", retries=3, to="aggregator")
    async def wiki(s):
        nonlocal count
        count += 1
        if count < 3:
            raise ValueError("fail")
        s.data.append(f"wiki_data_{count}")

    @app.step("news", retries=3, to="aggregator")
    async def news(s):
        s.data.append("news_data")

    @app.step("aggregator", to="streamer")
    async def agg(s):
        s.data.sort()

    @app.step("streamer")
    async def stream(s):
        yield "Hello"
        yield "World"
        yield f"Context: {', '.join(s.data)}"

    # Running it
    tokens = []
    async for event in app.run(state):
        if event.type == EventType.TOKEN:
            tokens.append(event.data)

    assert tokens == ["Hello", "World", "Context: news_data, wiki_data_3"]
