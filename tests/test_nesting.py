import pytest
from yaaf.types import AgentConfig, ExecContext
from yaaf.workflow import Workflow
from yaaf.funcs import as_middleware

# Fixtures
@pytest.fixture
def basic_ctx():
    return ExecContext(
        session_id="test_session",
        agent=AgentConfig(model_name="test-model"),
        input="start"
    )

@pytest.mark.asyncio
async def test_nested_workflow(basic_ctx):
    # Child Workflow
    child = Workflow()
    async def child_step(ctx):
        yield ctx.input + "_child"
    
    child.use(child_step)
    
    # Parent Workflow
    parent = Workflow()
    
    async def parent_start(ctx):
        return ctx.input + "_parent"
        
    parent.use(parent_start)
    parent.use(as_middleware(child))
    
    chunks = []
    async for chunk in parent.run_stream(basic_ctx):
        chunks.append(chunk)
        
    # Expect: start_parent_child
    assert chunks == ["start_parent_child"]

@pytest.mark.asyncio
async def test_nested_state_isolation(basic_ctx):
    # Test that child doesn't corrupt parent flow control, but might share state
    child = Workflow()
    async def child_step(ctx):
        ctx.goto("somewhere_that_doesnt_exist_in_parent")
        # yield nothing
    
    child.use(child_step)
    
    parent = Workflow()
    parent.use(as_middleware(child))
    
    # Should not crash
    await parent.run(basic_ctx)
    assert True
