import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Any
from justpipe import Pipe, EventType
from examples.utils import get_api_key, save_graph

try:
    from google import genai

    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False


@dataclass
class State:
    articles: List[str] = field(default_factory=list)
    summaries: List[str] = field(default_factory=list)


@dataclass
class Context:
    client: Any = None


pipe = Pipe[State, Context]()


@pipe.on_startup
async def setup(ctx: Context):
    """Initialize the Gemini client if an API key is provided."""
    api_key = get_api_key("GEMINI_API_KEY")
    if api_key and HAS_GENAI:
        # We store the client in context
        ctx.client = genai.Client(api_key=api_key)


@pipe.on_shutdown
async def cleanup(ctx: Context):
    """Close the Gemini client if it was initialized."""
    if ctx.client:
        ctx.client.close()


@pipe.step("start", to="fan_out")
async def start(state: State):
    """Prepare the list of articles to summarize."""
    state.articles = [
        "Python 3.13 released with new features like a specialized JIT compiler.",
        "AI models are getting smaller and faster with techniques like quantization.",
        "The weather tomorrow will be sunny with a chance of rain in the evening.",
    ]
    print(f"Found {len(state.articles)} articles to process.")


@pipe.map("fan_out", using="summarize", to="compile_report")
async def fan_out(state: State):
    """Spawn parallel summarization tasks for each article."""
    return state.articles


@pipe.step("summarize")
async def summarize(state: State, ctx: Context, article: str):
    """Summarize a single article using Gemini or a mock fallback."""
    summary = ""
    print(f"Processing: {article[:30]}...")

    if ctx.client and HAS_GENAI:
        try:
            # Use the native async methods via client.aio
            response = await ctx.client.aio.models.generate_content(
                model="gemini-2.0-flash",
                contents=f"Summarize this in one sentence: {article}",
            )
            summary = response.text.strip()
        except Exception as e:
            print(f"Gemini API Error: {e}")
            summary = f"Mock summary for: {article}"
    else:
        # Simulate work
        await asyncio.sleep(0.1)
        summary = f"Mock summary for: {article}"

    state.summaries.append(summary)


@pipe.step("compile_report")
async def compile_report(state: State):
    """Aggregate all summaries into a final report."""
    print("\n--- Final Report ---")
    print(f"Summarized {len(state.summaries)} articles:\n")
    for s in state.summaries:
        print(f"- {s}")


async def main():
    state = State()
    context = Context()

    print("Running News Summarizer Pipeline...")
    async for event in pipe.run(state, context, start="start"):
        if event.type == EventType.ERROR:
            print(f"Error in step {event.stage}: {event.data}")
    save_graph(pipe, Path(__file__).parent / "pipeline.mmd")


if __name__ == "__main__":
    asyncio.run(main())
