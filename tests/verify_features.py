import pytest
import logging
from yaaf.types import AgentConfig, ExecContext
from yaaf.workflows import Workflow
from yaaf.adapters import as_middleware

# Setup simple logging capture
logging.basicConfig(level=logging.INFO)

@pytest.fixture
def basic_ctx():
    return ExecContext(
        session_id="test",
        agent=AgentConfig(model_name="test"),
        input="start"
    )

@pytest.mark.asyncio
async def test_workflow_error_handling(basic_ctx):
    wf = Workflow()
    
    async def faulty_step(ctx):
        raise RuntimeError("Oops")
    
    wf.use(faulty_step)
    
    # Should catch, log, and re-raise
    with pytest.raises(RuntimeError, match="Oops"):
        await wf.run(basic_ctx)

@pytest.mark.asyncio
async def test_nested_logging(basic_ctx, caplog):
    # Caplog captures logs
    child = Workflow()
    async def child_step(ctx):
        ctx.input += "_child"
        return ctx
    child.use(child_step)
    
    parent = Workflow()
    parent.use(as_middleware(child))
    
    with caplog.at_level(logging.INFO):
        result = await parent.run(basic_ctx)
        
    assert result.input == "start_child"
    assert "Entering nested workflow" in caplog.text
    assert "Exiting nested workflow" in caplog.text

@pytest.mark.asyncio
async def test_nested_error_logging(basic_ctx, caplog):
    child = Workflow()
    async def child_fault(ctx):
        raise ValueError("ChildFail")
    child.use(child_fault)
    
    parent = Workflow()
    parent.use(as_middleware(child))
    
    with caplog.at_level(logging.ERROR):
        with pytest.raises(ValueError, match="ChildFail"):
            await parent.run(basic_ctx)
            
    assert "Nested workflow failed" in caplog.text
