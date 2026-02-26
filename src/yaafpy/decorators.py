from yaafpy.types import WorkflowAllowException, WorkflowAbortException, Transform, StreamHandler
import copy
import inspect
import functools
from typing import Callable

def stream_transform(fn):
    """
    Marca una función como un Transform válido para StreamWorkflow,
    asegurando que se trate como tal incluso si los nombres de los 
    parámetros varían.
    """
    @wraps(fn)
    async def wrapper(source, ctx):
        async for item in fn(source, ctx):
            yield item
    # Marcador interno para facilitar la detección en _is_transform
    wrapper._is_yaaf_transform = True
    return wrapper

def handler_to_transform(fn: StreamHandler) -> Transform:
    """
    Convierte un StreamHandler (item, ctx) en un Transform (source, ctx).
    Útil para reutilizar funciones simples en lógica de flujo complejo.
    """
    @functools.wraps(fn)
    async def wrapper(source, ctx):
        try:
            async for item in source:
                if ctx.stop:
                    break
                
                result = fn(item, ctx)
                
                # Soportar si el handler es async o devuelve generadores
                if inspect.isawaitable(result):
                    result = await result
                
                if inspect.isasyncgen(result):
                    async for sub in result:
                        yield sub
                else:
                    yield result
        finally:
            # Crucial para mantener los tests en PASSED
            if hasattr(source, "aclose"):
                await source.aclose()

    wrapper._is_yaaf_transform = True
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