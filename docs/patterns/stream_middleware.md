
### Middleware Example you need 


```
async def Preprocess_Stream_Step(ctx: ExecContext) -> ExecContext:
    source_stream = ctx.data  # capture BEFORE redefining

    async def gen() -> AsyncGenerator[Any, None]:
        async for item in source_stream:
            await asyncio.sleep(0.1)
            processed = item.upper()

            meta = ctx.shared_data.setdefault("metadata", {})
            meta.setdefault("preprocess", []).append({
                "input": item,
                "output": processed,
                "ts": time.time()
            })

            yield processed

    ctx.data = gen()
    return ctx

```