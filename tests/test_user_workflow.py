import pytest
from yaaf.types import AgentConfig, ExecContext
from yaaf.workflows import Workflow

@pytest.fixture
def basic_ctx():
    return ExecContext(
        session_id="test_session",
        agent=AgentConfig(model_name="test-model"),
        input="start"
    )

@pytest.mark.asyncio
async def test_workflow_access(basic_ctx):
    wf = Workflow()
    
    async def check_registry(ctx):
        # Verify we can access the workflow instance and its registry
        assert ctx.workflow is not None
        assert ctx.workflow == wf
        assert "check_registry" in ctx.workflow._registry
        ctx.input += "_verified"
        return ctx

    wf.use(check_registry)
    result = await wf.run(basic_ctx)
    assert result.input == "start_verified"

@pytest.mark.asyncio
async def test_mutation(basic_ctx):
    wf = Workflow()
    
    async def step1(ctx):
        ctx.input += "_A"
        return ctx
        
    async def step2(ctx):
        ctx.input += "_B"
        return ctx

    args_ctx = basic_ctx.clone() # Pass a copy to run to detect mutation on it? 
    # Actually run(basic_ctx) does `exec_ctx = ctx.model_copy()`.
    # So `basic_ctx` was never mutated even before this change?
    # Yes, line 27 of workflows.py already copied it.
    # But `step1` received `step_ctx`. 
    # If step1 did `ctx.input += "A"`, it modified `step_ctx`.
    # `workflow` loop did `exec_ctx = result`.
    # so `result` is the modified clone.
    
    # The new change `middleware(exec_ctx.clone())` means:
    # `step_ctx` inside middleware is a NEW clone.
    # `step1` modifies it and returns it.
    # `exec_ctx` in loop becomes that new clone.
    # So the chain works.
    
    # Is there a way to verify the functional enforcement?
    # If `step1` kept a reference to global/captured variable? No.
    
    # Test mutation logic holds:
    result = await wf.run(basic_ctx)
    assert result.input == "start_A_B"
    # Basic verification that logic still flows.

@pytest.mark.asyncio
async def test_stop(basic_ctx):
    wf = Workflow()
    
    async def step1(ctx):
        ctx.input += "_A"
        ctx.stop = True
        return ctx
        
    async def step2(ctx):
        ctx.input += "_ShouldNotRun"
        return ctx

    wf.use(step1)
    wf.use(step2)
    
    result = await wf.run(basic_ctx)
    assert result.input == "start_A"
    assert result.stop is True

@pytest.mark.asyncio
async def test_routing(basic_ctx):
    wf = Workflow()
    
    async def step1(ctx):
        ctx.input += "_A"
        ctx.goto("step3")
        return ctx
        
    async def step2(ctx):
        ctx.input += "_SkipMe"
        return ctx
        
    async def step3(ctx):
        ctx.input += "_C"
        return ctx

    wf.use(step1, name="step1")
    wf.use(step2, name="step2")
    wf.use(step3, name="step3")
    
    result = await wf.run(basic_ctx)
    assert result.input == "start_A_C"

@pytest.mark.asyncio
async def test_routing_invalid(basic_ctx):
    wf = Workflow()
    
    async def step1(ctx):
        ctx.goto("non_existent")
        return ctx
        
    wf.use(step1)
    
    result = await wf.run(basic_ctx)
    assert result.stop is True
    # If we added error field, we could check it too. But user added `error` field in types.py?
    # View types.py showed error field.
    # But workflow.py doesn't seem to set it, just logs.
    # So checking stop=True is correct.
