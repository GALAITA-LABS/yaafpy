import pytest
import asyncio
from typing import AsyncGenerator

from yaafpy.stream_flows import StreamWorkflow
from yaafpy.types import ExecContext


# ==========================================================
# Helpers
# ==========================================================

async def async_source():
    for i in range(3):
        yield i


async def collect(agen):
    result = []
    async for item in agen:
        result.append(item)
    return result


# ==========================================================
# use() + registry
# ==========================================================

def test_use_registers_with_name():
    wf = StreamWorkflow()

    async def transform(source, ctx):
        async for item in source:
            yield item

    wf.use(transform, name="t1", description="test transform")

    assert "t1" in wf._registry
    index, desc = wf._registry["t1"]
    assert index == 0
    assert desc == "test transform"


def test_use_registers_default_name():
    wf = StreamWorkflow()

    async def my_transform(source, ctx):
        async for item in source:
            yield item

    wf.use(my_transform)

    assert "my_transform" in wf._registry


# ==========================================================
# _is_transform
# ==========================================================

def test_is_transform_detects_valid_transform():
    wf = StreamWorkflow()

    async def transform(source, ctx):
        yield 1

    assert wf._is_transform(transform) is True


def test_is_transform_rejects_handler():
    wf = StreamWorkflow()

    async def handler(item, ctx):
        return item

    assert wf._is_transform(handler) is False


# ==========================================================
# StreamHandler wrapping
# ==========================================================

@pytest.mark.asyncio
async def test_sync_stream_handler():
    wf = StreamWorkflow()

    def handler(item, ctx):
        return item * 2

    wf.use(handler)

    result = await collect(wf.run(async_source()))
    assert result == [0, 2, 4]


@pytest.mark.asyncio
async def test_async_stream_handler():
    wf = StreamWorkflow()

    async def handler(item, ctx):
        return item + 10

    wf.use(handler)

    result = await collect(wf.run(async_source()))
    assert result == [10, 11, 12]


@pytest.mark.asyncio
async def test_handler_returning_async_generator():
    wf = StreamWorkflow()

    async def handler(item, ctx):
        async def subgen():
            yield item
            yield item * 100
        return subgen()

    wf.use(handler)

    result = await collect(wf.run(async_source()))
    assert result == [0, 0, 1, 100, 2, 200]


# ==========================================================
# Transform middleware (true Transform)
# ==========================================================

@pytest.mark.asyncio
async def test_transform_passthrough():
    wf = StreamWorkflow()

    async def transform(source, ctx):
        async for item in source:
            yield item * 3

    wf.use(transform)

    result = await collect(wf.run(async_source()))
    assert result == [0, 3, 6]


@pytest.mark.asyncio
async def test_chained_middlewares():
    wf = StreamWorkflow()

    def double(item, ctx):
        return item * 2

    async def add_one(source, ctx):
        async for item in source:
            yield item + 1

    wf.use(double)
    wf.use(add_one)

    result = await collect(wf.run(async_source()))
    assert result == [1, 3, 5]


# ==========================================================
# stop flag behavior
# ==========================================================

@pytest.mark.asyncio
async def test_stop_flag_interrupts_stream():
    wf = StreamWorkflow()

    def handler(item, ctx):
        if item == 1:
            ctx.stop = True
        return item

    wf.use(handler)

    result = await collect(wf.run(async_source()))
    assert result == [0, 1]  # stops after item 1


# ==========================================================
# stream closing
# ==========================================================

@pytest.mark.asyncio
async def test_stream_aclose_called():
    closed = False

    async def source():
        nonlocal closed
        try:
            for i in range(2):
                yield i
        finally:
            closed = True

    wf = StreamWorkflow()

    def handler(item, ctx):
        return item

    wf.use(handler)

    await collect(wf.run(source()))
    assert closed is True


# ==========================================================
# Context propagation
# ==========================================================

@pytest.mark.asyncio
async def test_context_shared_across_middlewares():
    wf = StreamWorkflow()

    def set_data(item, ctx):
        ctx.shared_data["seen"] = True
        return item

    def check_data(item, ctx):
        assert ctx.shared_data.get("seen") is True
        return item

    wf.use(set_data)
    wf.use(check_data)

    result = await collect(wf.run(async_source()))
    assert result == [0, 1, 2]


# ==========================================================
# run() with explicit context
# ==========================================================

@pytest.mark.asyncio
async def test_run_with_explicit_context():
    wf = StreamWorkflow()
    ctx = ExecContext()

    def handler(item, context):
        context.data = "updated"
        return item

    wf.use(handler)

    await collect(wf.run(async_source(), ctx=ctx))

    assert ctx.data == "updated"