import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import List
from justpipe import Pipe, EventType
from examples.utils import save_graph


@dataclass
class State:
    topic: str = ""
    facts: List[str] = field(default_factory=list)
    report: str = ""


# --- Sub-Pipeline: Researcher ---
research_pipe = Pipe[State, None]("Researcher")


@research_pipe.step("gather_facts")
async def gather_facts(state: State):
    print(f"  [Researcher] Researching topic: {state.topic}")
    await asyncio.sleep(0.1)
    state.facts.append(f"Fact 1 about {state.topic}")
    state.facts.append(f"Fact 2 about {state.topic}")
    print(f"  [Researcher] Found {len(state.facts)} facts.")


# --- Main Pipeline: Editor ---
main_pipe = Pipe[State, None]("Editor")


@main_pipe.step("assign_topic", to="delegate_research")
async def assign_topic(state: State):
    state.topic = "Quantum Computing"
    print(f"[Editor] Assigned topic: {state.topic}")


@main_pipe.sub("delegate_research", using=research_pipe, to="draft_report")
async def delegate_research(state: State):
    print("[Editor] Delegating to Researcher pipeline...")
    # Pass the state through to the sub-pipeline
    return state


@main_pipe.step("draft_report")
async def draft_report(state: State):
    print("[Editor] Drafting content...")
    state.report = f"Report on {state.topic}:\n" + "\n".join(
        f"- {f}" for f in state.facts
    )
    print(f"[Editor] Report compiled: {len(state.report)} chars.")


async def main():
    state = State()

    print("Starting Editor Pipeline...")
    async for event in main_pipe.run(state):
        # We can see events from sub-pipeline too!
        if event.type == EventType.STEP_START:
            print(f"-> Step started: {event.stage}")

    print("\n--- Final Output ---")
    print(state.report)

    save_graph(main_pipe, Path(__file__).parent / "pipeline.mmd")


if __name__ == "__main__":
    asyncio.run(main())
