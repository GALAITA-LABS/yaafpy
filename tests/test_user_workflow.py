import pytest
from yaafpy.types import AgentConfig, ExecContext
from yaafpy.workflows import Workflow

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
async def test_static_pipeline(basic_ctx):
    
    wf = Workflow()
    
    async def step1(ctx):
        ctx.input += "_step1"
        return ctx
        
    async def step2(ctx):
        ctx.input += "_step2"
        return ctx
        
    wf.use(step1)
    wf.use(step2)
    
    final_ctx = await wf.run(basic_ctx)
    assert final_ctx.input == "start_step1_step2"

