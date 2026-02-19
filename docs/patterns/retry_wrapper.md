def with_retry(target_middleware, attempts: int = 3, delay: float = 1.0):
    """
    Factory que envuelve a otro middleware para añadirle lógica de reintento.
    """
    @middleware # Usamos tu decorador estándar
    async def retry_wrapper(ctx: ExecContext):
        last_exception = None
        
        for attempt in range(attempts):
            try:
                # Intentamos ejecutar el middleware original
                # Pasamos una copia para que cada intento empiece "limpio"
                return await target_middleware(ctx)
                
            except (WorkflowAbortException, WorkflowAllowException):
                # Si el middleware decide abortar o saltar explícitamente, 
                # no reintentamos, respetamos su decisión.
                raise
                
            except Exception as e:
                last_exception = e
                logger.warning(
                    f"Intento {attempt + 1}/{attempts} fallido en "
                    f"{target_middleware.__name__}: {e}"
                )
                if attempt < attempts - 1:
                    await asyncio.sleep(delay)
        
        # Si agotamos los intentos, lanzamos el Abort que el motor entiende
        raise WorkflowAbortException(
            f"Superado el límite de reintentos ({attempts}) para "
            f"{target_middleware.__name__}. Último error: {last_exception}"
        )

    return retry_wrapper