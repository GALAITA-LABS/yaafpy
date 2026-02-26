from yaafpy.types import Transform
import inspect
from typing import Any, List, AsyncGenerator, Dict, Optional


from yaafpy.types import ExecContext, Transform, StreamHandler


class StreamWorkflow:
    """
    StreamWorkflow is a 100% async pipeline.

    CONTRACT:
    ----------
    - ctx.data must be:
        * AsyncGenerator
        * Iterable (list, tuple, etc.)
        * Simple value
    - Sync generators (Generator) are FORBIDDEN
      because they can block the event loop.
    """

    def __init__(self):
        self._middlewares: List[Transform] = []
        self._registry: Dict[str, tuple[int, Optional[str]]] = {}
        

    # ==========================================================
    # PUBLIC API
    # ==========================================================

    def use(self, middleware: [Transform, StreamHandler], name: Optional[str] = None, description: Optional[str] = None): 
        self._middlewares.append(middleware)
        if name:
            self._registry[name] = (len(self._middlewares) - 1, description)
        else:
            self._registry[middleware.__name__] = (len(self._middlewares) - 1, description)   
        return self


    async def run(self, source: AsyncGenerator[Any, None], ctx: Optional[ExecContext] = None) -> AsyncGenerator[Any, None]:
        
        stream = await self._build(source, ctx)
        
        try:
            async for item in stream:
                yield item
        finally:
            if hasattr(stream, "aclose"):
                await stream.aclose()

    
    # ==========================================================
    # INTERNALS
    # ==========================================================

   
    def _transform_handler(self, handler: StreamHandler) -> Transform:
        """
        Wrap a simple item handler(item, ctx) into a full AsyncGenerator Transform.
        Does NOT mutate ctx.data.
        """
        async def transform(source: AsyncGenerator[Any, None], ctx: ExecContext):
            async for item in source:

                if ctx.stop:
                    break

                result = handler(item, ctx)  # pass item explicitly

                if inspect.isawaitable(result):
                    result = await result

                # Support handler returning AsyncGenerator
                if inspect.isasyncgen(result):
                    async for sub in result:
                        yield sub
                else:   
                    yield result

        return transform


    async def _build(self, source: AsyncGenerator[Any, None], ctx: Optional[ExecContext] = None):
        if ctx is None:
            ctx = ExecContext(data=None)

        stream = source
        for handler in self._middlewares:
            # Detect dynamically si es Transform o StreamHandler
            if self._is_transform(handler):
                transform = handler
            else:
                transform = self._transform_handler(handler)

            # Aplicar la transformación
            stream = transform(stream, ctx)

        return stream

    def _is_transform(self, fn) -> bool:
        
        # Detecta async generator real
        sig = inspect.signature(fn)
        params = list(sig.parameters.keys())
        
        if inspect.isasyncgenfunction(fn) and len(params) >= 2 and params[0] == "source" and params[1] == "ctx":
            return True

        return False
        
        
