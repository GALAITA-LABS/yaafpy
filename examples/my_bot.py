import asyncio
from yaaf.types import AgentConfig, ExecContext
from yaaf.workflow import Workflow

# 1. Define Middlewares
async def logger_middleware(ctx: ExecContext):
    print(f"[Log] Processing: {ctx.input}")
    return ctx

async def echo_bot(ctx: ExecContext):
    """Simple bot logic: if 'hello', reply greeting. else 'echo'."""
    user_msg = str(ctx.input).lower()
    
    if "hello" in user_msg:
        print("[Bot] User said hello!")
        ctx.input = "Hello there! How can I help?"
        ctx.stop = True # Done
    else:
        ctx.input = f"Echo: {ctx.input}"
        
    return ctx

async def router_middleware(ctx: ExecContext):
    """Routes to 'special' if input contains 'secret'."""
    if "secret" in str(ctx.input):
        print("[Router] Moving to secret area...")
        ctx.goto("special_handler")
    return ctx

async def special_handler(ctx: ExecContext):
    ctx.input = "*** ACCESS GRANTED ***"
    return ctx

# 2. Main execution
async def main():
    # Setup
    config = AgentConfig(model_name="gpt-4")
    ctx = ExecContext(session_id="123", agent=config, input="This is a secret message")
    
    # Workflow Construction
    wf = Workflow()
    wf.use(logger_middleware)
    wf.use(router_middleware)
    wf.use(echo_bot) # Will be skipped if routed
    wf.use(special_handler, name="special_handler")
    wf.use(logger_middleware) # Log result
    
    print("--- Running Workflow ---")
    result = await wf.run(ctx)
    print(f"--- Final Result: {result.input} ---")

if __name__ == "__main__":
    asyncio.run(main())
