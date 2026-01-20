from yaaf.types import ExecContext
import json

async def inject_history(ctx: ExecContext):
    """
    Middleware to inject conversation history based on session_id.
    """
    session_id = ctx.session_id
    # Mock DB Fetch
    # history = db.get(session_id)
    print(f"[Memory] Fetching history for session {session_id}")
    mock_history = ["User: Hello", "Agent: Hi there"]
    
    ctx.state['history'] = mock_history
    # Returns None (Static middleware) -> updates ctx in place

async def persist_state(ctx: ExecContext):
    """
    Middleware to save the state at the end of execution.
    """
    # Mock DB Save
    print(f"[Memory] Persisting state for session {ctx.session_id}")
    
    # Serialize
    data = ctx.model_dump_json()
    # db.save(ctx.session_id, data)
    print(f"[Memory] Saved: {len(data)} bytes")
