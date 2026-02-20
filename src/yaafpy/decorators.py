from yaafpy.types import WorkflowAllowException, WorkflowAbortException
import copy
import inspect
import functools
from typing import Callable


def stream_transform(handler: Callable):
    """
    Especializado en transformar items. 
    Envuelve el generador actual y captura errores del stream.
    """
    @functools.wraps(handler)
    async def wrapper(ctx: 'ExecContext') -> 'ExecContext':
        if ctx.stop or not inspect.isasyncgen(ctx.data):
            return ctx

        source_gen = ctx.data

        async def pipeline_wrapper():
            try:
                async for item in source_gen:
                    
                    res = await handler(item) if inspect.iscoroutinefunction(handler) else handler(item)
                    
                    if res is not None:
                        yield res
            except Exception as e:
                # Si el stream falla (red, parsing, etc), abortamos el workflow
                raise WorkflowAbortException(f"Stream failure in {handler.__name__}: {e}") from e
            finally:
                # Cierre en cascada: asegura que el generador anterior se libere
                await source_gen.aclose()

        ctx.data = pipeline_wrapper()
        return ctx
        
    return wrapper

def middleware(func):
    @functools.wraps(func)
    async def wrapper(ctx: 'ExecContext'):
        
        if ctx.stop:
            return ctx

        # Shadow copy: si el middleware falla a mitad, 
        # devolvemos esta versión limpia al motor.
        ctx_copy = copy.copy(ctx)

        try:
            result = func(ctx_copy)
            exec_ctx = await result if inspect.isawaitable(result) else result

            if exec_ctx is None:
                raise ValueError(f"Middleware '{func.__name__}' retornó None")
            
            return exec_ctx

        except WorkflowAllowException:
            # Caso "Skip": devolvemos el contexto previo (ctx_copy)
            # El motor simplemente incrementará el cursor y seguirá.
            return ctx_copy

        except WorkflowAbortException:
            # Caso "Freno Manual": el desarrollador sabe lo que hace.
            # Dejamos que suba al motor para activar el finally.
            raise

        except Exception as e:
            # Caso "Accidente": no controlado. 
            # Forzamos un Abort por seguridad (Diseño Defensivo).
            raise WorkflowAbortException(
                f"Excepción no controlada en {func.__name__}: {str(e)}"
            ) from e
            
    return wrapper