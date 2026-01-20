import asyncio
from dataclasses import dataclass
from pathlib import Path
from justpipe import Pipe, EventType
from examples.utils import get_api_key, save_graph

from typing import Any

try:
    from openai import AsyncOpenAI

    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


@dataclass
class State:
    prompt: str = ""
    response: str = ""


@dataclass
class Context:
    client: Any = None


pipe = Pipe[State, Context]()


@pipe.on_startup
async def setup(ctx: Context):
    key = get_api_key("OPENAI_API_KEY")
    if key and HAS_OPENAI:
        ctx.client = AsyncOpenAI(api_key=key)


@pipe.on_shutdown
async def cleanup(ctx: Context):
    if ctx.client:
        await ctx.client.close()


@pipe.step("start", to="respond")
async def start(state: State):
    print(f"User asking: {state.prompt}")


@pipe.step("respond")
async def respond(state: State, ctx: Context):
    print("Generating response...")

    if ctx.client:
        try:
            stream = await ctx.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a wise philosopher."},
                    {"role": "user", "content": state.prompt},
                ],
                stream=True,
            )
            async for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    state.response += content
                    yield content
            return
        except Exception as e:
            print(f"OpenAI API Error: {e}")
            # Fallback to mock
            pass

    # Mock behavior
    mock_tokens = ["Thinking", "...", " ", "Life", " ", "is", " ", "complexity", "."]
    for token in mock_tokens:
        await asyncio.sleep(0.1)
        state.response += token
        yield token


async def main():
    state = State(prompt="What is the meaning of life?")
    context = Context()

    print("--- Streaming Chatbot ---")
    async for event in pipe.run(state, context):
        if event.type == EventType.TOKEN:
            print(f"Received token: {event.data!r}")

    print(f"\nFull Response: {state.response}")
    save_graph(pipe, Path(__file__).parent / "pipeline.mmd")


if __name__ == "__main__":
    asyncio.run(main())
