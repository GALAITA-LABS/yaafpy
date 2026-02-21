import inspect
import functools
import asyncio
from typing import Any, List, AsyncGenerator, Dict, Optional
from collections.abc import Iterable

from yaafpy.types import ExecContext, Middleware


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
        self._middlewares: List[Middleware] = []
        self._registry: Dict[str, tuple[int, Optional[str]]] = {}
        

    # ==========================================================
    # PUBLIC API
    # ==========================================================

    def use(self, middleware: Middleware, name: Optional[str] = None, description: Optional[str] = None): 
        self._middlewares.append(middleware)
        if name:
            self._registry[name] = (len(self._middlewares) - 1, description)
        else:
            self._registry[middleware.__name__] = (len(self._middlewares) - 1, description)   
        return self

    async def run(self, ctx: ExecContext) -> AsyncGenerator[Any, None]:
        """
        Construye la tubería lazy y devuelve el AsyncGenerator final.
        """
 
        # Ensure ctx.workflow
        ctx.workflow = self

        # Normalize the initial stream under strict async contract
        ctx.data = await self._ensure_async_stream(ctx.data)

        # Build onion (lazy chain)
        for mw in self._middlewares:
            transformer = self._stream_transform(mw)
            ctx = await transformer(ctx)

        # Execute the final stream
        try:
            async for chunk in ctx.data:
                yield chunk
        finally:
            if hasattr(ctx.data, "aclose"):
                await ctx.data.aclose()

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

        # already AsyncGenerator
        if inspect.isasyncgen(data):
            return data

        # Generator síncrono → PROHIBIDO
        if inspect.isgenerator(data):
            raise TypeError(
                "Sync generators are not allowed in StreamWorkflow. "
                "They may block the event loop. "
                "Use async generators instead."
            )

        # Iterable (no string)
        if isinstance(data, Iterable) and not isinstance(data, (str, bytes)):

            async def iterable_wrapper():
                for item in data:
                    yield item

            return iterable_wrapper()

        # simple value → seed async
        async def seed():
            yield data

        return seed()

    def _stream_transform(
        self, handler: Middleware
    ) -> Middleware:
        """
        Envuelve el handler para construir la capa onion.
        Cada middleware transforma el stream anterior.
        """

        @functools.wraps(handler)
        async def wrapper(ctx: ExecContext) -> ExecContext:
            source_gen = ctx.data

            async def pipeline_wrapper() -> AsyncGenerator[Any, None]:
                try:
                    async for item in source_gen:
                        try:
                            # Execute handler (sync or async)
                            if inspect.isawaitable(handler):
                                res = await handler(item)
                            else:
                                res = handler(item)
                        except asyncio.CancelledError:
                            # Propagar cancelación correctamente
                            raise
                        except Exception as e:
                            # Agregar contexto, pero mantener tipo original
                            raise RuntimeError(
                                  f"Error in middleware '{handler.__name__}': {e}"
                            ) from e

                        # Flatten async generator
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
                    # Cascade close
                    if hasattr(source_gen, "aclose"):
                        try:
                            await source_gen.aclose()
                        except RuntimeError:
                            pass  # Already closed, safe to ignore


            ctx.data = pipeline_wrapper()
            return ctx

        return wrapper
