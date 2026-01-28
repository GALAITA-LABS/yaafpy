from typing import Any, Dict, Optional, List, Tuple
from pydantic import BaseModel, Field, PrivateAttr

"""
Allows skipping a specific middleware and continues with the normal execution path.
Use this when a middleware should be conditionally bypassed without interrupting the workflow.
"""
class WorkflowAllowException(Exception):
    """Exception raised for a middleware execption that allow the execution to continue"""

    def __init__(self, message):
        super().__init__(message)
"""
Propagates a stop flag that immediately terminates execution and prevents any follow-up runs.
Use this when the workflow must be explicitly halted.
"""        
class WorkflowAbortException(Exception):
    """Exception raised for Abort execution of the all workflow"""

    def __init__(self, message):
        super().__init__(message)        






class AgentConfig(BaseModel):
    """
    Holds static configuration for an Agent.
    """
    model: str = Field(default="", description="The name of the LLM model to use")
    prompt: str = Field(default="", description="The system prompt for the agent")
    temperature: float = Field(default=0.7, description="Sampling temperature")
    tools: List[Dict[str, Any]] = Field(default_factory=list, description="List of tool definitions")
    name: Optional[str] = Field(default=None, description="The name of the agent")
    description: Optional[str] = Field(default=None, description="A description of the agent")
    # Allow extra configuration
    model_config = {"extra": "allow"}


class ExecContext(BaseModel):
    """
    The mutable state carrier for the workflow. Every step have the own ExecContext
    """
    session_id: Optional[str] = Field(default=None, description="Unique identifier for the session")
    input: Any = Field(default=None, description="The data seed most likely from user")
    output: Any = Field(default=None, description="The computation output for the current step or middleware. Use as input for the next step (Recommended)")
    agent: AgentConfig = Field(..., description="The configuration currently in use")
    state: Dict[str, Any] = Field(default_factory=dict, description="Utility bag for store computations and bussines logic")
    storage: Dict[str, Any] = Field(default_factory=dict, description="Ephemeral storage for current run")
    stop: bool = Field(default=False, description="Flag to stop execution")
    error: Optional[str] = Field(default=None, description="Error message")
    steps: int = Field(default=0, description="Number of steps executed")
    tokens: int = Field(default=0, description="Number of tokens used")
    
    # Private fields for internal flow control
    cursor: int = Field(default=0)
    trace: List[Tuple[str, Any]] = Field(default_factory=list) # Execution trace or trajectory.
    jump_to: Optional[str] = Field(default=None)
    workflow: Optional[Any] = Field(default=None)

