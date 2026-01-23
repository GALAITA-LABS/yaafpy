# YAAF (Yet Another Agentic Framework)

A stream-first, middleware-based Python framework for building agentic AI flows.

## Features
- **Flexible**: You can use any LLM, tools, and storage.
- **Functional Programming Approach**: Use composable and reusable middleware to build a workflow.
- **Stream Architecture Available**: Also Built for streaming pipelines.
- **Nested Workflows**: Compose complex behaviors by nesting workflows.
- **Type Safe**: Built with Pydantic for validation and serialization.

## Installation
```bash
pip install yaaf
```

## Quick Start
```python
import asyncio
from yaaf.types import AgentConfig, ExecContext
from yaaf.workflows import Workflow

async def echo_step(ctx):
    ctx.input = f"Echo: {ctx.input}"
    return ctx

async def main():
    wf = Workflow()
    wf.use(echo_step)    
    ctx = ExecContext(session_id="test", agent=AgentConfig(model="gpt-4"), input="Hello")
    result = await wf.run(ctx)
    print(result.input)

if __name__ == "__main__":
    asyncio.run(main())
```
