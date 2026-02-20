import inspect
import functools
import asyncio
from typing import Any, List, Callable, AsyncGenerator, Dict, Optional
from collections.abc import Iterable

from yaafpy.types import ExecContext




class StreamWorkflow:
    """
    StreamWorkflow es un pipeline 100% async.

    CONTRATO:
    ----------
    - ctx.data debe ser:
        * AsyncGenerator
        * Iterable pequeño (list, tuple, etc.)
        * Valor simple
    - Sync generators (Generator) están PROHIBIDOS
      porque pueden bloquear el event loop.
    """

    def __init__(self):
        self._middlewares: List[Callable] = []
        self._registry: Dict[str, tuple[int, Optional[str]]] = {}

    # ==========================================================
    # PUBLIC API
    # ==========================================================

    def use(self, middleware: Callable):
        self._middlewares.append(middleware)
        return self

    async def run(self, ctx: ExecContext) -> AsyncGenerator[Any, None]:
        """
        Construye la tubería lazy y devuelve el AsyncGenerator final.
        """

        # asure ctx.workflow
        ctx.workflow = self

        # 1️⃣ Normalizar el stream inicial bajo contrato async estricto
        ctx.data = await self._ensure_async_stream(ctx.data)

        # 2️⃣ Construcción onion (lazy chain)
        for mw in self._middlewares:
            transformer = self._stream_transform(mw)
            ctx = await transformer(ctx)

        # 3️⃣ Ejecutar el stream final
        async for chunk in ctx.data:
            yield chunk

    # ==========================================================
    # INTERNALS
    # ==========================================================

    async def _ensure_async_stream(
        self, data: Any
    ) -> AsyncGenerator[Any, None]:
        """
        Garantiza que data sea AsyncGenerator.

        Permitido:
            - AsyncGenerator
            - Iterable pequeño
            - Valor simple

        Prohibido:
            - Generator síncrono (bloqueante)
        """

        # 1️⃣ Ya es AsyncGenerator
        if inspect.isasyncgen(data):
            return data

        # 2️⃣ Generator síncrono → PROHIBIDO
        if inspect.isgenerator(data):
            raise TypeError(
                "Sync generators are not allowed in StreamWorkflow. "
                "They may block the event loop. "
                "Use async generators instead."
            )

        # 3️⃣ Iterable (no string)
        if isinstance(data, Iterable) and not isinstance(data, (str, bytes)):

            async def iterable_wrapper():
                for item in data:
                    yield item

            return iterable_wrapper()

        # 4️⃣ Valor simple → seed async
        async def seed():
            yield data

        return seed()

    def _stream_transform(
        self, handler: Callable
    ) -> Callable[[ExecContext], ExecContext]:
        """
        Envuelve el handler para construir la capa onion.
        Cada middleware transforma el stream anterior.
        """

        @functools.wraps(handler)
        async def wrapper(ctx: ExecContext) -> ExecContext:
            if ctx.stop:
                return ctx

            source_gen = ctx.data

            async def pipeline_wrapper() -> AsyncGenerator[Any, None]:
                try:
                    async for item in source_gen:

                        if ctx.stop:
                            break

                        # Ejecutar handler (sync o async)
                        if inspect.iscoroutinefunction(handler):
                            res = await handler(item, ctx)
                        else:
                            res = handler(item, ctx)

                        # 🔥 APLANADO
                        if inspect.isasyncgen(res):
                            async for sub_item in res:
                                yield sub_item
                        elif res is not None:
                            yield res

                except Exception as e:
                    raise RuntimeError(
                        f"Stream failure in {handler.__name__}: {e}"
                    ) from e

                finally:
                    # Cierre en cascada
                    if hasattr(source_gen, "aclose"):
                        await source_gen.aclose()

            ctx.data = pipeline_wrapper()
            return ctx

        return wrapper