import pytest
from yaaf.types import AgentConfig, ExecContext
from yaaf.workflows import Workflow
from yaaf.adapters import as_middleware

@pytest.fixture
def basic_ctx():
    return ExecContext(
        session_id="test",
        agent=AgentConfig(model_name="test"),
        input="Start"
    )

@pytest.mark.asyncio
async def test_nesting_batch(basic_ctx):
    # Child
    child = Workflow()
    async def child_step(ctx):
        ctx.input += "_Child"
        return ctx
    child.use(child_step)
    
    # Parent
    parent = Workflow()
    async def parent_step(ctx):
        ctx.input += "_Parent"
        return ctx
        
    parent.use(parent_step)
    parent.use(as_middleware(child))
    
    result = await parent.run(basic_ctx)
    assert result.input == "Start_Parent_Child"

@pytest.mark.asyncio
async def test_nesting_deep(basic_ctx):
    # Grandchild
    gc = Workflow()
    async def gc_step(ctx):
        ctx.input += "_GC"
        return ctx
    gc.use(gc_step)
    
    # Child uses Grandchild
    child = Workflow()
    child.use(as_middleware(gc))
    
    # Parent uses Child
    parent = Workflow()
    parent.use(as_middleware(child))
    
    result = await parent.run(basic_ctx)
    assert result.input == "Start_GC"
