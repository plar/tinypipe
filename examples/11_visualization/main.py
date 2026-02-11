import asyncio
from pathlib import Path
from justpipe import Pipe
from examples.utils import save_graph

# 1. Define a sub-pipeline
sub_pipe = Pipe(name="SubPipeline")


@sub_pipe.step("sub_step_1", to="sub_step_2")
async def sub_step_1(state):
    pass


@sub_pipe.step("sub_step_2")
async def sub_step_2(state):
    pass


# 2. Define the main pipeline
pipe = Pipe(name="MainPipeline")


@pipe.step("input", to=["process_a", "process_b"])
async def input_step(state):
    pass


@pipe.step("process_a", to="join")
async def process_a(state):
    pass


@pipe.step("process_b", to="sub_flow")
async def process_b(state):
    pass


@pipe.sub("sub_flow", pipeline=sub_pipe, to="join")
async def sub_flow(state):
    return state


@pipe.step("join", to="output")
async def join_step(state):
    pass


@pipe.step("output")
async def output_step(state):
    pass


async def main():
    print("Generating Mermaid graph for a complex pipeline...")

    # You don't even need to run the pipe to generate the graph!
    # pipe.graph() inspects the registered steps and topology.
    graph_code = pipe.graph()

    print("\nGenerated Mermaid Code:")
    print("-" * 20)
    print(graph_code)
    print("-" * 20)

    save_graph(pipe, Path(__file__).parent / "pipeline.mmd")
    print("\nMermaid graph generated successfully.")


if __name__ == "__main__":
    asyncio.run(main())
