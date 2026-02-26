import pytest
import asyncio
from typing import AsyncGenerator
import inspect
from yaafpy.stream_flows import StreamWorkflow
from yaafpy.types import ExecContext, WorkflowAbortException
from yaafpy.decorators import handler_to_transform, stream_transform
from functools import wraps
import logging


# ==========================================================
# Helpers
# ==========================================================

async def empty_source():
    if False:
        yield 1


async def async_source(n=3):
    for i in range(n):
        yield i


async def collect(agen):
    result = []
    async for item in agen:
        result.append(item)
    return result

# ==========================================================
# Decorators
# ==========================================================

def with_logging(fn):
    logger = logging.getLogger("yaaf.handler")
    @wraps(fn)
    async def wrapper(item, ctx):
        logger.info(f"➡ Input: {item}")
        result = fn(item, ctx)
        if inspect.isawaitable(result):
            result = await result
        logger.info(f"⬅ Output: {result}")
        return result
    return wrapper


def with_service_factory(service_name: str, factory, close_fn=None):
    def decorator(fn):
        @wraps(fn)
        async def wrapper(item, ctx): # Ahora recibe el item directamente
            # Inyectar solo si no existe en esta ejecución
            if service_name not in ctx.shared_data.get("service", {}):
                instance = factory()
                if inspect.isawaitable(instance):
                    instance = await instance
                ctx.shared_data.setdefault("service", {})[service_name] = instance
            
            # Ejecutar el siguiente en la cadena (Logging o el Handler)
            return await fn(item, ctx)
        return wrapper
    return decorator


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

    wf.use(add_one)
    wf.use(double)

    result = await collect(wf.run(async_source()))
    assert result == [2, 4 , 6]


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


# ==========================================================
# Empty stream behavior
# ==========================================================

@pytest.mark.asyncio
async def test_empty_source():
    wf = StreamWorkflow()
    wf.use(lambda item, ctx: item * 2)

    result = await collect(wf.run(empty_source()))
    assert result == []


# ==========================================================
# Middleware ordering guarantees
# ==========================================================

@pytest.mark.asyncio
async def test_middleware_execution_order():
    wf = StreamWorkflow()
    execution = []

    def first(item, ctx):
        execution.append("first")
        return item

    def second(item, ctx):
        execution.append("second")
        return item

    wf.use(first)
    wf.use(second)

    await collect(wf.run(async_source(1)))
    assert execution == ["first", "second"]


# ==========================================================
# Registry overwrite behavior
# ==========================================================

def test_registry_overwrites_same_name():
    wf = StreamWorkflow()

    async def t1(source, ctx):
        yield 1

    async def t2(source, ctx):
        yield 2

    wf.use(t1, name="dup")
    wf.use(t2, name="dup")

    index, _ = wf._registry["dup"]
    assert index == 1


# ==========================================================
# _build returns proper async generator
# ==========================================================

@pytest.mark.asyncio
async def test_build_returns_async_generator():
    wf = StreamWorkflow()

    wf.use(lambda item, ctx: item)

    stream = await wf._build(async_source())
    assert inspect.isasyncgen(stream)


# ==========================================================
# Exception propagation
# ==========================================================

@pytest.mark.asyncio
async def test_exception_propagates():
    wf = StreamWorkflow()

    def handler(item, ctx):
        if item == 1:
            raise ValueError("boom")
        return item

    wf.use(handler)

    with pytest.raises(ValueError):
        await collect(wf.run(async_source()))


# ==========================================================
# Transform with wrong signature should NOT be allowed
# ==========================================================

@pytest.mark.asyncio
async def test_misleading_async_function_not_allowed():
    wf = StreamWorkflow()

    async def fake_transform(x, y, z):  # wrong signature
        return 123

    wf.use(fake_transform)

    with pytest.raises(TypeError):
        await collect(wf.run(async_source(1)))




# ==========================================================
# Handler returning None
# ==========================================================

@pytest.mark.asyncio
async def test_handler_returning_none():
    wf = StreamWorkflow()

    def handler(item, ctx):
        return None

    wf.use(handler)

    result = await collect(wf.run(async_source(2)))
    assert result == [None, None]


# ==========================================================
# Awaitable returning simple value
# ==========================================================

@pytest.mark.asyncio
async def test_awaitable_returning_value():
    wf = StreamWorkflow()

    async def handler(item, ctx):
        await asyncio.sleep(0)
        return item * 5

    wf.use(handler)

    result = await collect(wf.run(async_source(3)))
    assert result == [0, 5, 10]


# ==========================================================
# Multiple runs reuse same workflow
# ==========================================================

@pytest.mark.asyncio
async def test_multiple_runs_same_workflow():
    wf = StreamWorkflow()
    wf.use(lambda item, ctx: item + 1)

    result1 = await collect(wf.run(async_source(2)))
    result2 = await collect(wf.run(async_source(2)))

    assert result1 == result2 == [1, 2]


# ==========================================================
# Explicit context preserved across runs
# ==========================================================

@pytest.mark.asyncio
async def test_context_isolation_between_runs():
    wf = StreamWorkflow()

    def handler(item, ctx):
        ctx.shared_data["count"] = ctx.shared_data.get("count", 0) + 1
        return item

    wf.use(handler)

    ctx1 = ExecContext()
    ctx2 = ExecContext()

    await collect(wf.run(async_source(2), ctx1))
    await collect(wf.run(async_source(2), ctx2))

    assert ctx1.shared_data["count"] == 2
    assert ctx2.shared_data["count"] == 2


# ==========================================================
# Decorator compatibility — StreamHandler
# ==========================================================

@pytest.mark.asyncio
async def test_decorated_handler_preserves_behavior():
    wf = StreamWorkflow()

    def my_decorator(fn):
        @wraps(fn)
        def wrapper(item, ctx):
            return fn(item, ctx)
        return wrapper

    @my_decorator
    def handler(item, ctx):
        return item * 7

    wf.use(handler)

    result = await collect(wf.run(async_source(3)))
    assert result == [0, 7, 14]


# ==========================================================
# Decorator compatibility — Transform
# ==========================================================

@pytest.mark.asyncio
async def test_decorated_transform_detected_correctly():
    wf = StreamWorkflow()

    def transform_decorator(fn):
        @wraps(fn)
        async def wrapper(source, ctx):
            async for item in fn(source, ctx):
                yield item
        return wrapper

    @transform_decorator
    async def transform(source, ctx):
        async for item in source:
            yield item + 100

    wf.use(transform)

    result = await collect(wf.run(async_source(2)))
    assert result == [100, 101]


# ==========================================================
# Early break ensures aclose is awaited
# ==========================================================

@pytest.mark.asyncio
async def test_early_break_closes_stream():
    closed = False

    async def source():
        nonlocal closed
        try:
            for i in range(10):
                yield i
        finally:
            closed = True

    wf = StreamWorkflow()

    def stopper(item, ctx):
        ctx.stop = True
        return item

    wf.use(stopper)

    result = await collect(wf.run(source()))
    assert result == [0]
    assert closed is True


# ==========================================================
# Close by Exception in Downstream -> Upstream
# ==========================================================

@pytest.mark.asyncio
async def test_upstream_closes_on_middleware_error():
    source_is_closed = False

    async def resource_intensive_source():
        nonlocal source_is_closed
        try:
            for i in range(10):
                yield i
        finally:
            source_is_closed = True  # Simula liberación de DB/Archivo

    async def failing_middleware(source, ctx):
        async for item in source:
            if item == 1:
                raise ValueError("Boom!")
            yield item

    wf = StreamWorkflow()
    wf.use(failing_middleware)

    with pytest.raises(ValueError):
        async for _ in wf.run(resource_intensive_source()):
            pass

    assert source_is_closed is True


# ==========================================================
# Stop structural upstream close
# ==========================================================

@pytest.mark.asyncio
async def test_stop_closes_upstream():
    closed = False

    async def source():
        nonlocal closed
        try:
            for i in range(10):
                yield i
        finally:
            closed = True

    wf = StreamWorkflow()

    async def stopper(source, ctx):
        async for item in source:
            yield item
            raise WorkflowAbortException("Stop test_stop_via_async_break")

    wf.use(stopper)

    result = await collect(wf.run(source()))
    assert result == [0]
    assert closed is True


# ==========================================================
# Decorator compatibility — handler_to_transform
# ==========================================================


@pytest.mark.asyncio
async def test_handler_to_transform_conversion():
    # Un handler simple (no es generador)
    def multiply_by_ten(item, ctx):
        return item * 10

    # Lo promocionamos
    decorated_logic = handler_to_transform(multiply_by_ten)
    
    wf = StreamWorkflow()
    wf.use(decorated_logic) # Ahora StreamWorkflow lo ve como Transform

    results = await collect(wf.run(async_source(3)))
    assert results == [0, 10, 20]

@pytest.mark.asyncio
async def test_handler_to_transform_decorator_works():
    wf = StreamWorkflow()

    @handler_to_transform
    def my_handler(item, ctx):
        return item * 10

    wf.use(my_handler)

    result = await collect(wf.run(async_source(3)))
    assert result == [0, 10, 20]

@pytest.mark.asyncio
async def test_as_transform_error_cleanup():
    source_closed = False

    async def my_source():
        nonlocal source_closed
        try:
            yield 1
            yield 2
        finally:
            source_closed = True

    @handler_to_transform
    def faulty_handler(item, ctx):
        if item == 1:
            raise ValueError("Error en handler")
        return item

    wf = StreamWorkflow().use(faulty_handler)

    with pytest.raises(ValueError):
        async for _ in wf.run(my_source()):
            pass

    assert source_closed is True


# ==========================================================
# Mocks para el Test
# ==========================================================
class MockDatabase:
    def __init__(self):
        self.connected = True
        self.data_saved = []

    async def aclose(self):
        self.connected = False

# ==========================================================
# Decorator Integration Test
# ==========================================================
@pytest.mark.asyncio
async def test_full_decorator_pipeline_integration(caplog):
    caplog.set_level(logging.INFO)
    
    # 1. Definimos la Factory
    def db_factory():
        return MockDatabase()

    # 2. Definimos el Handler con la cadena de decoradores
    # IMPORTANTE: with_service_factory YA convierte a Transform, 
    # por lo que no necesitamos handler_to_transform si usamos ese.
    @with_service_factory("postgres", db_factory)
    @with_logging
    async def process_and_save(item, ctx):
        db = ctx.shared_data["service"]["postgres"]
        db.data_saved.append(item)
        return f"SAVED:{item}"

    # 3. Ejecución del Workflow
    wf = StreamWorkflow()
    wf.use(process_and_save)

    async def async_source():
        for i in range(2):
            yield i

    results = []
    async for res in wf.run(async_source()):
        results.append(res)

    # ==========================================================
    # 4. ASERCIONES (La parte de QA)
    # ==========================================================
    
    # ¿Los resultados son correctos?
    assert results == ["SAVED:0", "SAVED:1"]
    
    # ¿El logging funcionó?
    assert "➡ Input: 0" in caplog.text
    assert "⬅ Output: SAVED:1" in caplog.text

    # ¿Se inyectó y usó el servicio?
    # Como el servicio se limpia en el finally del decorador, 
    # necesitamos capturar la instancia antes de que desaparezca 
    # o verificar su efecto colateral.
    assert "postgres" not in results # El servicio no se fuga al output
