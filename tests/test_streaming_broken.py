import pytest
import inspect
from yaaf.types import AgentConfig, ExecContext
from yaaf.workflow import Workflow

@pytest.fixture
def basic_ctx():
    return ExecContext(
        session_id="test",
        agent=AgentConfig(model_name="test"),
        input="start"
    )

@pytest.mark.asyncio
async def test_streaming_attempt(basic_ctx):
    wf = Workflow()
    
    async def stream_step(ctx):
        yield "chunk1"
        yield "chunk2"
        # Logic: return ctx? Generator doesn't return ctx in same way.
    
    wf.use(stream_step)
    
    # This calls stream_step(ctx) -> returns AsyncGenerator
    # run() checks isawaitable(gen) -> False
    # exec_ctx = gen
    # Next loop: middleware(gen) -> Crash?
    # Or if it's the last step, run() returns gen.
    
    result = await wf.run(basic_ctx)
    
    # If it returns generator, we can iterate?
    if inspect.isasyncgen(result):
        chunks = [c async for c in result]
        assert chunks == ["chunk1", "chunk2"]
    else:
        # If it returns ExecContext, streaming failed?
        assert False, f"Expected AsyncGenerator, got {type(result)}"
