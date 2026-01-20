import logging
import inspect
from typing import Callable, List, Dict, Optional, Any, AsyncGenerator, Awaitable
from yaaf.types import ExecContext

logger = logging.getLogger("yaaf.workflow")

class Workflow:
    def __init__(self):
        self._middleware: List[Callable[[ExecContext], Awaitable[ExecContext]]] = []
        self._registry: Dict[str, int] = {}

    def use(self, middleware: Callable[[ExecContext], Awaitable[ExecContext]], name: Optional[str] = None):
        self._middleware.append(middleware)
        if name:
            self._registry[name] = len(self._middleware) - 1
        else:
            self._registry[middleware.__name__] = len(self._middleware) - 1    
        return self


    async def run(self, ctx: Optional[ExecContext] = None) -> ExecContext:
    

        if ctx is None:
            exec_ctx = ExecContext(_workflow=self)
        elif ctx._jump_to and self._registry.get(ctx._jump_to) is None: 
            raise ValueError("Jump target is not valid")   
        else:
            exec_ctx = ctx.model_copy(deep=True)

        exec_ctx._workflow = self

        if exec_ctx.stop:
            return exec_ctx
        
        if exec_ctx._jump_to is None:
            cursor = 0
        else:
            cursor = self._registry[exec_ctx._jump_to]

        n = len(self._middleware)


        while cursor < n:
            try:
                # Force functional approach: 
                # Pass a COPY of the context so middleware cannot mutate the loop's reference in-place
                result = self._middleware[cursor](exec_ctx.model_copy(deep=True))
                
                if inspect.isawaitable(result):
                   exec_ctx = await result
                else:
                   exec_ctx = result
                
                if exec_ctx.stop:
                    return exec_ctx

                if exec_ctx._jump_to and self._registry.get(exec_ctx._jump_to) is None:
                    raise ValueError(f"Jump target {exec_ctx._jump_to} not found in registry")

                if exec_ctx._jump_to:
                    cursor = self._registry[exec_ctx._jump_to]
                    exec_ctx._jump_to = None
                else:
                    cursor +=1 
            
            except Exception as e:
                logger.error(f"[Workflow Error] Step index {cursor} failed: {e}")
                exec_ctx.stop = True
                return exec_ctx 
            
        return exec_ctx 
            

