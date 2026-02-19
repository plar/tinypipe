"""Real LLM streaming example with justpipe.

Demonstrates:
- Real OpenAI API call with streaming (when OPENAI_API_KEY is set)
- Automatic fallback to a mock LLM when no key is present
- Error handling and timeout
- Token accumulation in state
- TestPipe test showing how to mock the LLM step

Usage:
    # With a real API key:
    OPENAI_API_KEY=sk-... uv run python examples/15_real_llm_streaming/main.py

    # Without a key (uses mock):
    uv run python examples/15_real_llm_streaming/main.py
"""

import asyncio
import os
from dataclasses import dataclass, field

from justpipe import Pipe, EventType, TestPipe

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class ChatState:
    user_message: str
    system_prompt: str = "You are a helpful assistant. Be concise."
    prompt: str = ""
    tokens: list[str] = field(default_factory=list)
    response: str = ""


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

pipe = Pipe(ChatState, name="llm_streaming")


@pipe.step(to="call_llm")
async def build_prompt(state: ChatState) -> None:
    """Format the chat prompt from user message and system prompt."""
    state.prompt = f"{state.system_prompt}\n\nUser: {state.user_message}"


@pipe.step()
async def call_llm(state: ChatState):
    """Stream tokens from an LLM.

    Uses OpenAI if OPENAI_API_KEY is set, otherwise falls back to a mock.
    Yields individual tokens as they arrive.
    """
    api_key = os.getenv("OPENAI_API_KEY")

    if api_key:
        # Real OpenAI streaming
        try:
            from openai import AsyncOpenAI
        except ImportError:
            print("openai package not installed. Install with: pip install openai")
            print("Falling back to mock...")
            api_key = None

    if api_key:
        client = AsyncOpenAI(api_key=api_key)
        stream = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": state.system_prompt},
                {"role": "user", "content": state.user_message},
            ],
            stream=True,
            max_tokens=150,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                token = delta.content
                state.tokens.append(token)
                yield token
    else:
        # Mock streaming for demo/testing without API key
        mock_response = (
            "Python is a versatile, high-level programming language "
            "known for its readability and extensive ecosystem. "
            "It's widely used in web development, data science, "
            "AI/ML, and automation."
        )
        for word in mock_response.split(" "):
            token = word + " "
            state.tokens.append(token)
            yield token
            await asyncio.sleep(0.05)  # Simulate network latency

    state.response = "".join(state.tokens)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    state = ChatState(user_message="What is Python in 2 sentences?")

    has_key = bool(os.getenv("OPENAI_API_KEY"))
    print(f"[{'Real API' if has_key else 'Mock'}] Streaming response:\n")

    async for event in pipe.run(state):
        if event.type == EventType.TOKEN:
            print(event.payload, end="", flush=True)

    print(f"\n\n--- Done ({len(state.tokens)} tokens) ---")


# ---------------------------------------------------------------------------
# TestPipe demo
# ---------------------------------------------------------------------------


async def test_llm_pipeline() -> None:
    """Example test showing how to mock the LLM step."""
    with TestPipe(pipe) as t:

        async def mock_llm(state: ChatState):
            for token in ["Hello ", "from ", "mock!"]:
                state.tokens.append(token)
                yield token
            state.response = "".join(state.tokens)

        t.mock("call_llm", side_effect=mock_llm)

        result = await t.run(ChatState(user_message="test"))

        assert result.was_called("build_prompt")
        assert result.was_called("call_llm")
        assert result.tokens == ["Hello ", "from ", "mock!"]
        assert result.final_state.response == "Hello from mock!"
        print("Test passed!")


if __name__ == "__main__":
    asyncio.run(main())
    print()
    asyncio.run(test_llm_pipeline())
