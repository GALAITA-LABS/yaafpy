## Inyección de Dependencias Específicas
  Imagina que tienes un middleware que guarda datos en una base de datos, pero quieres usarlo para diferentes tablas o servicios dentro del mismo flujo.

```
def persistence_factory(table_name: str, schema: str = "public"):
    @middleware
    async def middleware_instance(ctx: ExecContext):
        # El middleware ya sabe a qué tabla escribir sin buscar en shared_data
        db = ctx.shared_data.get("db_connection")
        await db.execute(f"INSERT INTO {schema}.{table_name} VALUES (%s)", ctx.data)
        return ctx
    return middleware_instance

# Configuración: Reutilizamos la lógica, cambiamos el destino
wf.add(persistence_factory(table_name="logs", schema="system"))
wf.add(persistence_factory(table_name="orders", schema="sales"))


### Para loger y trazas
```
def logger_middleware(prefix: str):
    """
    Esta es la función 'Factory' o 'Wrapper'. 
    Recibe parámetros que no son el contexto.
    """
    @middleware # Aplicamos el decorador aquí mismo
    async def decorator(ctx: ExecContext):
        print(f"{prefix}: Procesando dato {ctx.data}")
        return ctx
        
    return decorator


# Uso al configurar el workflow:
wf = SecuencialWorkflow()
wf.add(logger_middleware(prefix="USER_SERVICE"))
wf.add(logger_middleware(prefix="AUTH_SERVICE"))

```
### Es posible anidar varios factories si crecen mucho o son comunes unirlos en uno.

def with_logger(prefix: str, target):
    @middleware
    async def logger_wrapper(ctx: ExecContext):
        print(f"[{prefix}] Iniciando...")
        ctx = await target(ctx) # Ejecuta lo que hay dentro
        print(f"[{prefix}] Finalizado.")
        return ctx
    return logger_wrapper

def with_timer(target):
    @middleware
    async def timer_wrapper(ctx: ExecContext):
        start = time.perf_counter()
        ctx = await target(ctx)
        end = time.perf_counter()
        print(f"Tiempo de ejecución: {end - start:.4f}s")
        return ctx
    return timer_wrapper

def standard_service_wrapper(target):
    """Aplica los 3 estándares de la empresa a cualquier middleware"""
    return with_logger("SVC", with_timer(with_retry(target)))

# Uso limpio
wf.add(standard_service_wrapper(mi_logica_de_negocio))


Orden de ejecución claro: La ejecución va de afuera hacia adentro (como una cebolla). El primer factory en la lista es el primero en recibir el ctx y el último en devolverlo.