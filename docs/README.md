# justpipe Documentation

Welcome to the technical documentation for `justpipe`. This directory contains deep-dives into the library's architecture, core concepts, and practical guides for building production-grade pipelines.

## 🏛️ Architecture
Understand the inner workings of the execution engine.

- **[Runtime Kernel](./architecture/kernel.md)**: Deep-dive into the async event loop, the `ExecutionPlan`, and the internal orchestrator.

## 💡 Core Concepts
Master the mental model and behavioral contracts of the library.

- **[Observability & Events](./concepts/observability.md)**: Details on the event schema, v1.0 fields, and lineage tracking.
- **[Terminal Semantics](./concepts/terminal_semantics.md)**: How pipelines finish, failure classification (Kind vs Source), and diagnostic payloads.

## 🛠️ Practical Guides
How-to guides for common development tasks.

- **[Concurrency & State](./guides/concurrency.md)**: Best practices for managing mutable vs immutable state in parallel flows.
- **[Middleware](./guides/middleware.md)**: Learn how to wrap steps for logging, retries, and auth.
- **[Lifecycle Hooks](./guides/lifecycle_hooks.md)**: Managing external resources like DBs and API clients.

## 🧪 Testing
How to ensure your pipelines are reliable and bug-free.

- **[Testing Harness (TestPipe)](./guides/testing/harness.md)**: Using the built-in harness to mock steps and assert on event sequences.
- **[Fuzz Testing](./guides/testing/fuzz_testing.md)**: Leveraging property-based testing to find edge cases in your graph topology.

---

### Other Resources
- **[Examples Gallery](../examples/README.md)**: A collection of runnable code snippets for common patterns.
- **[Quick Start](../README.md#quickstart-ai-search-pipeline)**: Get up and running in 5 minutes.
