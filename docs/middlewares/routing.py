from yaaf.types import ExecContext

async def llm_router(ctx: ExecContext):
    """
    Decides the next step using a LLM classification.
    """
    # Mock LLM decision
    # decision = llm.predict(ctx.input, ctx.state)
    
    print("[Router] Analyzing flow...")
    
    # Simple mock logic for demonstration
    # If input contains "end", go to cleanup (optional logic)
    # Here we just demonstrate goto usage.
    
    # For now, we won't jump unless we have a specific condition, 
    # to avoid infinite loops in simple tests.
    pass

async def logic_router(ctx: ExecContext):
    """
    Decides the next step using a Execution Context Logic base in input, output, error, state, etc.
    """
    
    print("[Router] Analyzing flow...")
    
    # Simple mock logic for demonstration
    # If input contains "end", go to cleanup (optional logic)
    # Here we just demonstrate goto usage.
    
    # For now, we won't jump unless we have a specific condition, 
    # to avoid infinite loops in simple tests.
    pass
