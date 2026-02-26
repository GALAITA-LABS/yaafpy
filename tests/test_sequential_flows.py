import pytest
import asyncio
from yaafpy.sequential_flows import Workflow
from yaafpy.types import ExecContext, WorkflowAbortException


# =========================
# BASIC EXECUTION TESTS
# =========================

@pytest.mark.asyncio
async def test_sequential_execution():
    wf = Workflow()

    async def mw1(ctx):
        ctx.data += 1
        return ctx

    async def mw2(ctx):
        ctx.data *= 2
        return ctx

    wf.use(mw1).use(mw2)

    ctx = ExecContext(data=1)
    result = await wf.run(ctx)

    assert result.data == 4  # (1+1)*2


@pytest.mark.asyncio
async def test_workflow_callable():
    wf = Workflow()

    async def mw(ctx):
        ctx.data = "ok"
        return ctx

    wf.use(mw)

    ctx = ExecContext(data=None)
    result = await wf(ctx)

    assert result.data == "ok"


@pytest.mark.asyncio
async def test_empty_workflow():
    wf = Workflow()
    ctx = ExecContext(data=123)

    result = await wf.run(ctx)

    assert result.data == 123


# =========================
# STOP LOGIC
# =========================

@pytest.mark.asyncio
async def test_stop_flag_stops_execution():
    wf = Workflow()

    async def mw1(ctx):
        ctx.stop = True
        return ctx

    async def mw2(ctx):
        ctx.data = "should not run"
        return ctx

    wf.use(mw1).use(mw2)

    ctx = ExecContext(data=None)
    result = await wf.run(ctx)

    assert result.stop is True
    assert result.data is None


# =========================
# JUMP LOGIC
# =========================

@pytest.mark.asyncio
async def test_valid_jump():
    wf = Workflow()

    async def mw1(ctx):
        ctx.jump_to = "mw3"
        return ctx

    async def mw2(ctx):
        ctx.data = "wrong"
        return ctx

    async def mw3(ctx):
        ctx.data = "correct"
        return ctx

    wf.use(mw1, name="mw1")
    wf.use(mw2, name="mw2")
    wf.use(mw3, name="mw3")

    ctx = ExecContext(data=None)
    result = await wf.run(ctx)

    assert result.data == "correct"


@pytest.mark.asyncio
async def test_invalid_jump_raises_abort():
    wf = Workflow()

    async def mw(ctx):
        ctx.jump_to = "does_not_exist"
        return ctx

    wf.use(mw, name="mw")

    ctx = ExecContext(data=None)

    with pytest.raises(WorkflowAbortException):
        await wf.run(ctx)


@pytest.mark.asyncio
async def test_jump_with_async_generator_raises():
    wf = Workflow()

    async def async_gen():
        yield 1

    async def mw(ctx):
        ctx.data = async_gen()
        ctx.jump_to = "mw"
        return ctx

    wf.use(mw, name="mw")

    ctx = ExecContext(data=None)

    with pytest.raises(RuntimeError):
        await wf.run(ctx)


@pytest.mark.asyncio
async def test_start_with_jump_to():
    wf = Workflow()

    async def mw1(ctx):
        ctx.data = "wrong"
        return ctx

    async def mw2(ctx):
        ctx.data = "correct"
        return ctx

    wf.use(mw1, name="mw1")
    wf.use(mw2, name="mw2")

    ctx = ExecContext(data=None, jump_to="mw2")

    result = await wf.run(ctx)

    assert result.data == "correct"


# =========================
# ABORT BEHAVIOR
# =========================

@pytest.mark.asyncio
async def test_abort_exception_sets_stop():
    wf = Workflow()

    async def mw(ctx):
        raise WorkflowAbortException("abort")

    wf.use(mw)

    ctx = ExecContext(data=None)

    with pytest.raises(WorkflowAbortException):
        await wf.run(ctx)

    assert ctx.stop is True


@pytest.mark.asyncio
async def test_unexpected_exception():
    wf = Workflow()
   
    async def mw(ctx):
        raise ValueError("unexpected")

    wf.use(mw)

    ctx = ExecContext(data=None)

    with pytest.raises(ValueError):
        await wf.run(ctx)






# =========================
# GENERATOR LEAK
# =========================

@pytest.mark.asyncio
async def test_generator_leak_detection():
    wf = Workflow()

    async def async_gen():
        yield 1

    async def mw(ctx):
        ctx.data = async_gen()
        return ctx

    wf.use(mw)

    with pytest.raises(RuntimeError):
        await wf.run(ExecContext(data=None))


# =========================
# REGISTRY TESTS
# =========================

@pytest.mark.asyncio
async def test_registry_with_name():
    wf = Workflow()

    async def mw(ctx):
        return ctx

    wf.use(mw, name="custom")

    assert "custom" in wf._registry


@pytest.mark.asyncio
async def test_registry_without_name_uses_function_name():
    wf = Workflow()

    async def my_middleware(ctx):
        return ctx

    wf.use(my_middleware)

    assert "my_middleware" in wf._registry


# =========================
# Running Twice Same Workflow
# =========================

@pytest.mark.asyncio
async def test_run_twice_same_instance():
    wf = Workflow()

    async def mw(ctx):
        ctx.data += 1
        return ctx

    wf.use(mw)

    result1 = await wf.run(ExecContext(data=1))
    result2 = await wf.run(ExecContext(data=1))

    assert result1.data == 2
    assert result2.data == 2

# =========================
# Concurrency Safety Race Conditions
# =========================

@pytest.mark.asyncio
async def test_parallel_runs():
    wf = Workflow()

    async def mw(ctx):
        await asyncio.sleep(0.01)
        ctx.data += 1
        return ctx

    wf.use(mw)

    async def run_one():
        return await wf.run(ExecContext(data=1))

    results = await asyncio.gather(
        run_one(),
        run_one(),
        run_one(),
    )

    assert all(r.data == 2 for r in results)

# =========================
# Jump to Non-Existing Middleware
# =========================

@pytest.mark.asyncio
async def test_jump_to_non_existing_middleware():
    wf = Workflow()

    async def mw(ctx):
        ctx.jump_to = "non_existing"
        return ctx

    wf.use(mw)

    with pytest.raises(WorkflowAbortException):
        await wf.run(ExecContext(data=None))

# =========================
# Memory Profilling Tests
# =========================

import tracemalloc

@pytest.mark.asyncio
async def test_memory_stability():
    wf = Workflow()

    async def mw(ctx):
        return ctx

    wf.use(mw)

    tracemalloc.start()

    for _ in range(1000):
        await wf.run(ExecContext(data=None))

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Adjust threshold as needed
    assert peak < 10_000_000  # 10MB

# =========================
# Performance Tests
# =========================

import time

@pytest.mark.asyncio
async def test_performance():
    wf = Workflow()

    async def mw(ctx):
        return ctx

    wf.use(mw)

    start = time.time()
    await wf.run(ExecContext(data=None))
    end = time.time()

    assert end - start < 1  # 1 second
