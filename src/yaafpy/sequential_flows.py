import logging
import inspect
from typing import Callable, List, Dict, Optional, Awaitable, TypeAlias, Union
from yaafpy.types import ExecContext, WorkflowAbortException, Middleware

logger = logging.getLogger("yaaf.workflow")



class Workflow:
    def __init__(self):
        self._middleware: List[Middleware] = []
        self._registry: Dict[str, tuple[int, Optional[str]]] = {}
        

    async def __call__(self, ctx: ExecContext) -> ExecContext:
        """Allows the workflow to be used as a middleware."""
        return await self.run(ctx)


    def use(self, middleware: Middleware, name: Optional[str] = None, description: Optional[str] = None): # Coul be interesting add description to the middlewares
        self._middleware.append(middleware)
        if name:
            self._registry[name] = (len(self._middleware) - 1, description)
        else:
            self._registry[middleware.__name__] = (len(self._middleware) - 1, description)   
        return self

    async def run(self, ctx: Optional[ExecContext] = None) -> ExecContext:
            
            exec_ctx = ctx if ctx is not None else ExecContext()
            exec_ctx.workflow = self
            
            # Determinamos inicio (cursor)
            cursor = 0 if exec_ctx.jump_to is None else self._registry[exec_ctx.jump_to][0]
            exec_ctx.jump_to = None
            
            n = len(self._middleware)

            try:
                while cursor < n:
                    
                    # El decorador garantiza que aquí siempre recibimos un ExecContext 
                    # o se lanza una WorkflowAbortException.
                    exec_ctx = await self._middleware[cursor](exec_ctx)

                    if exec_ctx.stop:
                        return exec_ctx

                    # Jump logic (Only solid data)
                    if exec_ctx.jump_to:
                        if inspect.isasyncgen(exec_ctx.data):
                            raise RuntimeError("Jump is not allowed with active generators.")
                        
                        # 2. Validate the existence of the destination
                        if exec_ctx.jump_to not in self._registry:
                            # Abort with a message that helps the developer
                            raise WorkflowAbortException(
                                f"Invalid jump: The destination '{exec_ctx.jump_to}' does not exist in the registry. "
                                f"Available destinations: {list(self._registry.keys())}"
                            )
                        
                        cursor = self._registry[exec_ctx.jump_to][0]
                        exec_ctx.jump_to = None
                        continue

                    cursor += 1

                # Final Integrity Validation
                if inspect.isasyncgen(exec_ctx.data):
                    raise RuntimeError("Generator leak detected at the end of the flow.")

            except WorkflowAbortException:
                # The abort rises here, marks the stop and the finally cleans everything.
                exec_ctx.stop = True
                raise 

            
            return exec_ctx
            

