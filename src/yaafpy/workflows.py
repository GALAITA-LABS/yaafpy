import logging
import inspect
from typing import Callable, List, Dict, Optional, Any, AsyncGenerator, Awaitable, TypeAlias, Union
from yaafpy.adapters import normalize_step_result
from yaafpy.types import ExecContext, WorkflowAbortException

logger = logging.getLogger("yaaf.workflow")

Middleware: TypeAlias = Callable[
    [ExecContext],
    Union[ExecContext, Awaitable[ExecContext]]
]

class Workflow:
    def __init__(self):
        self._middleware: List[Middleware] = []
        self._registry: Dict[str, int] = {}
        self._description: List[str] = []
        self._cleanup_tasks: List[Callable] = []

    async def __call__(self, ctx: ExecContext) -> ExecContext:
        """Permite que el workflow se use como un middleware."""
        return await self.run(ctx)

    def register_cleanup(self, task: Callable):
        """
        Registra una tarea de limpieza que se ejecutará al finalizar el flujo.
        """
        self._cleanup_tasks.append(task)

    def use(self, middleware: Middleware, name: Optional[str] = None, description: Optional[str] = None): # Coul be interesting add description to the middlewares
        self._middleware.append(middleware)
        self._description.append(description)
        if name:
            self._registry[name] = len(self._middleware) - 1
        else:
            self._registry[middleware.__name__] = len(self._middleware) - 1    
        return self


    async def _execute_cleanup(self):
        """
        Ejecuta todas las tareas de limpieza registradas en el contexto.
        Maneja tanto funciones síncronas como asíncronas.
        """
        if not hasattr(self, '_cleanup_tasks') or not self._cleanup_tasks:
            return

        logger.info(f"Iniciando limpieza de {len(self._cleanup_tasks)} tareas...")
        
        # Ejecutamos en orden inverso (LIFO)
        while self._cleanup_tasks:
            task = self._cleanup_tasks.pop()
            try:
                if inspect.iscoroutinefunction(task):
                    await task()
                elif callable(task):
                    task()
            except Exception as e:
                # No permitimos que un fallo en un cleanup detenga los demás
                logger.error(f"Error en tarea de limpieza: {e}")


    async def run(self, ctx: Optional[ExecContext] = None) -> ExecContext:
            
            exec_ctx = ctx if ctx is not None else ExecContext()
            exec_ctx.workflow = self
            
            # Determinamos inicio (cursor)
            cursor = 0 if exec_ctx.jump_to is None else self._registry[exec_ctx.jump_to]
            exec_ctx.jump_to = None
            
            n = len(self._middleware)

            try:
                while cursor < n:
                    
                    # El decorador garantiza que aquí siempre recibimos un ExecContext 
                    # o se lanza una WorkflowAbortException.
                    exec_ctx = await self._middleware[cursor](exec_ctx)

                    if exec_ctx.stop:
                        return exec_ctx

                    # Lógica de Jump (Solo datos sólidos)
                    if exec_ctx.jump_to:
                        if inspect.isasyncgen(exec_ctx.data):
                            raise RuntimeError("No se permite Jump con generadores activos.")
                        
                        # 2. Validamos la existencia del destino
                        if exec_ctx.jump_to not in self._registry:
                            # Abortamos con un mensaje que ayude al desarrollador
                            raise WorkflowAbortException(
                                f"Salto inválido: El destino '{exec_ctx.jump_to}' no existe en el registro. "
                                f"Destinos disponibles: {list(self._registry.keys())}"
                            )
                        
                        cursor = self._registry[exec_ctx.jump_to]
                        exec_ctx.jump_to = None
                        continue

                    cursor += 1

                # Validación Final de Integridad
                if inspect.isasyncgen(exec_ctx.data):
                    raise RuntimeError("Fuga de generador detectada al final del flujo.")

            except WorkflowAbortException:
                # El aborto sube aquí, marca el stop y el finally limpia todo.
                exec_ctx.stop = True
                raise 

            finally:
                # Limpieza de recursos registrados por los middlewares (DB, archivos, etc.)
                await self._execute_cleanup()
            
            return exec_ctx
            

