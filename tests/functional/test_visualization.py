"""Tests for Mermaid diagram generation."""

from tinypipe import Pipe


def test_graph_generation():
    """Test basic graph structure with nodes, edges, Start/End."""
    pipe = Pipe()

    @pipe.step("a", to="b")
    async def step_a():
        pass

    @pipe.step("b", to=["c", "d"])
    async def step_b():
        pass

    @pipe.step("c")
    async def step_c():
        pass

    @pipe.step("d")
    async def step_d():
        pass

    graph = pipe.graph()

    # Basic structure
    assert "graph TD" in graph
    assert "Start" in graph
    assert "End" in graph

    # Nodes exist
    assert "n0" in graph  # a
    assert "n1" in graph  # b

    # Edges
    assert "Start -->" in graph
    assert "--> End" in graph

    # Styling
    assert "classDef step" in graph
    assert "classDef startEnd" in graph


def test_graph_with_streaming_steps():
    """Test that streaming steps are marked with ⚡."""
    pipe = Pipe()

    @pipe.step("start", to="stream")
    async def start():
        pass

    @pipe.step("stream", to="end_step")
    async def stream():
        yield "token"

    @pipe.step("end_step")
    async def end_step():
        pass

    graph = pipe.graph()

    # Streaming step has ⚡ marker
    assert "⚡" in graph
    assert "classDef streaming" in graph


def test_graph_with_isolated_steps():
    """Test that isolated steps are grouped in Utilities subgraph."""
    pipe = Pipe()

    @pipe.step("connected", to="next_step")
    async def connected():
        pass

    @pipe.step("next_step")
    async def next_step():
        pass

    @pipe.step("orphan")
    async def orphan():
        pass

    graph = pipe.graph()

    # Isolated step in utilities subgraph
    assert "subgraph utilities" in graph
    assert "Orphan" in graph  # Title case
    assert "classDef isolated" in graph


def test_graph_parallel_branches():
    """Test that parallel branches are grouped in subgraphs."""
    pipe = Pipe()

    @pipe.step("entry", to=["branch_a", "branch_b"])
    async def entry():
        pass

    @pipe.step("branch_a", to="merge")
    async def branch_a():
        pass

    @pipe.step("branch_b", to="merge")
    async def branch_b():
        pass

    @pipe.step("merge")
    async def merge():
        pass

    graph = pipe.graph()

    # Parallel subgraph exists
    assert "subgraph parallel" in graph
    assert "direction LR" in graph  # Horizontal layout for parallel


def test_rag_pipeline_graph():
    """
    Test a realistic RAG (Retrieval-Augmented Generation) pipeline.

    This demonstrates a production-ready AI pipeline with:
    - Query processing and embedding
    - Parallel retrieval from multiple sources
    - Context assembly and ranking
    - Streaming LLM response generation
    - Utility functions for caching/logging
    """
    pipe = Pipe()

    # === INGESTION ===
    @pipe.step("parse_query", to="embed_query")
    async def parse_query(state):
        """Parse and normalize the user query."""
        pass

    @pipe.step(
        "embed_query", to=["search_vectors", "search_knowledge_graph", "search_web"]
    )
    async def embed_query(state):
        """Generate embeddings for semantic search."""
        pass

    # === PARALLEL RETRIEVAL ===
    @pipe.step("search_vectors", to="rank_results")
    async def search_vectors(state):
        """Search vector database (Pinecone/Weaviate/etc)."""
        yield "Searching vectors..."

    @pipe.step("search_knowledge_graph", to="rank_results")
    async def search_knowledge_graph(state):
        """Query knowledge graph (Neo4j/etc)."""
        pass

    @pipe.step("search_web", to="rank_results")
    async def search_web(state):
        """Real-time web search (Tavily/Serper/etc)."""
        yield "Searching web..."

    # === CONTEXT ASSEMBLY ===
    @pipe.step("rank_results", to="build_context")
    async def rank_results(state):
        """Rank and deduplicate retrieved results."""
        pass

    @pipe.step("build_context", to="generate_response")
    async def build_context(state):
        """Assemble context window for LLM."""
        pass

    # === GENERATION ===
    @pipe.step("generate_response", to="format_output")
    async def generate_response(state):
        """Stream response from LLM (GPT-4/Claude/etc)."""
        yield "Generating..."
        yield "response..."
        yield "tokens..."

    @pipe.step("format_output")
    async def format_output(state):
        """Format final response with citations."""
        yield "**Answer:** ..."

    # === UTILITIES (not in main flow) ===
    @pipe.step("cache_manager")
    async def cache_manager(state):
        """Manage query/response cache."""
        pass

    @pipe.step("analytics_logger")
    async def analytics_logger(state):
        """Log metrics and traces."""
        yield "logging..."

    # Generate the graph
    graph = pipe.graph()

    # === ASSERTIONS ===

    # Structure
    assert "graph TD" in graph
    assert "Start" in graph
    assert "End" in graph

    # Entry point
    assert "Parse Query" in graph

    # Parallel retrieval subgraph
    assert "subgraph parallel" in graph
    assert "Search Vectors" in graph
    assert "Search Knowledge Graph" in graph
    assert "Search Web" in graph

    # Streaming steps marked
    assert graph.count("⚡") >= 4  # vectors, web, generate, format, analytics

    # Utilities subgraph
    assert "subgraph utilities" in graph
    assert "Cache Manager" in graph
    assert "Analytics Logger" in graph

    # Styling
    assert "classDef step" in graph
    assert "classDef streaming" in graph
    assert "classDef isolated" in graph
    assert "classDef startEnd" in graph

    # This graph is documentation-ready!
    # Uncomment to see the full output:
    # print("\n" + "=" * 60)
    # print("RAG Pipeline Diagram")
    # print("=" * 60)
    # print(graph)
