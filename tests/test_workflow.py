import pytest
import asyncio
from yaaf.types import AgentConfig, ExecContext
from yaaf.workflow import Workflow

# Fixtures
@pytest.fixture
def basic_ctx():
    return ExecContext(
        session_id="test_session",
        agent=AgentConfig(model_name="test-model"),
        input="initial_input"
    )

@pytest.mark.asyncio
async def test_static_pipeline(basic_ctx):
    wf = Workflow()
    
    async def step1(ctx):
        return ctx.input + "_step1"
        
    async def step2(ctx):
        return ctx.input + "_step2"
        
    wf.use(step1)
    wf.use(step2)
    
    final_ctx = await wf.run(basic_ctx)
    assert final_ctx.input == "initial_input_step1_step2"

@pytest.mark.asyncio
async def test_streaming_pipeline(basic_ctx):
    wf = Workflow()
    
    async def generator_step(ctx):
        # Consume input and yield chunks
        yield "chunk1"
        yield "chunk2"
        
    # We need to test if the generator is properly consumable by the caller of run_stream
    wf.use(generator_step)
    
    # run_stream should yield chunk1, chunk2
    chunks = []
    async for chunk in wf.run_stream(basic_ctx):
        chunks.append(chunk)
        
    assert chunks == ["chunk1", "chunk2"]

@pytest.mark.asyncio
async def test_mixed_pipeline(basic_ctx):
    wf = Workflow()
    
    async def static_step(ctx):
        return "processed"
        
    async def stream_step(ctx):
        yield ctx.input + "_1"
        yield ctx.input + "_2"
        
    wf.use(static_step)
    wf.use(stream_step)
    
    chunks = []
    async for chunk in wf.run_stream(basic_ctx):
        chunks.append(chunk)
        
    assert chunks == ["processed_1", "processed_2"]

@pytest.mark.asyncio
async def test_routing(basic_ctx):
    wf = Workflow()
    
    async def start(ctx):
        # Jump to step3
        ctx.goto("step3")
        return ctx.input + "_start"
        
    async def step2(ctx):
        return ctx.input + "_skipped"
        
    async def step3(ctx):
        return ctx.input + "_end"
        
    wf.use(start, name="start")
    wf.use(step2, name="step2")
    wf.use(step3, name="step3")
    
    final_ctx = await wf.run(basic_ctx)
    assert "skipped" not in final_ctx.input
    assert final_ctx.input == "initial_input_start_end"
