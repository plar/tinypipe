import asyncio
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List
from justpipe import Pipe, EventType, Suspend
from examples.utils import save_graph


class Result(Enum):
    CORRECT = "correct"
    FORBIDDEN = "forbidden"


@dataclass
class GameState:
    questions: List[str] = field(
        default_factory=lambda: [
            "Is the sky blue?",
            "Is coal white?",
            "Do you like programming?",
            "Is this a pipe?",
            "Are you a robot?",
        ]
    )
    current_question_idx: int = 0
    user_input: str = ""
    is_game_over: bool = False
    error_message: str = ""


pipe = Pipe[GameState, None]()


@pipe.step("ask_question")
async def ask_question(state: GameState):
    if state.current_question_idx >= len(state.questions):
        print("\n[Game] You've answered all questions! You win!")
        state.is_game_over = True
        return

    question = state.questions[state.current_question_idx]
    print(f"\n[Game] Question {state.current_question_idx + 1}: {question}")

    # Suspend execution to wait for external input
    return Suspend(reason="wait_for_user_input")


@pipe.switch(
    "check_answer",
    routes={
        Result.CORRECT: "ask_question",
        Result.FORBIDDEN: "game_over",
    },
)
async def check_answer(state: GameState):
    forbidden = ["yes", "no", "black", "white"]
    answer = state.user_input.strip().lower()

    if answer in forbidden:
        state.is_game_over = True
        state.error_message = f"Forbidden word '{answer}' used!"
        return Result.FORBIDDEN

    print(f"[Game] '{state.user_input}' is a safe answer. Moving on...")
    state.current_question_idx += 1
    return Result.CORRECT


@pipe.step("game_over")
async def game_over(state: GameState):
    print(f"\n[Game Over] {state.error_message}")


async def main():
    state = GameState()

    print("Welcome to 'Yes, No, Black, White'!")
    print("Rules: Answer the questions without using the forbidden words.")

    # We start at the 'ask_question' step
    current_step = "ask_question"

    while not state.is_game_over:
        # Run the pipeline until it finishes or suspends
        async for event in pipe.run(state, start=current_step):
            if event.type == EventType.SUSPEND:
                # The pipeline has paused. Now we can interact with the user.
                print(">> Input: ", end="", flush=True)
                # In a real app, this might be a web request or message queue
                # Here we use sys.stdin.readline() to support our test harness
                line = sys.stdin.readline()
                if not line:
                    state.is_game_over = True
                    break
                state.user_input = line.strip()

                # Resume from the next logical step
                current_step = "check_answer"

            elif event.type == EventType.ERROR:
                print(f"Pipeline Error: {event.data}")
                state.is_game_over = True

    save_graph(pipe, Path(__file__).parent / "pipeline.mmd")


if __name__ == "__main__":
    asyncio.run(main())
