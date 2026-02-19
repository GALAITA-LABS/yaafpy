from yaafpy.types import WorkflowAllowException, WorkflowAbortException
import copy
import inspect
import functools

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