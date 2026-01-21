from typing import Any, Dict, Optional, List, Tuple
from pydantic import BaseModel, Field, PrivateAttr

class AgentConfig(BaseModel):
    """
    Holds static configuration for an Agent.
    """
    model_name: str = Field(..., description="The name of the LLM model to use")
    prompt: str = Field(default="", description="The system prompt for the agent")
    temperature: float = Field(default=0.7, description="Sampling temperature")
    tools: List[Dict[str, Any]] = Field(default_factory=list, description="List of tool definitions")
    
    # Allow extra configuration
    model_config = {"extra": "allow"}


class ExecContext(BaseModel):
    """
    The mutable state carrier for the workflow. Every step have the own ExecContext
    """
    session_id: str = Field(..., description="Unique identifier for the session")
    input: Any = Field(default=None, description="The data entering the current step")
    output: Any = Field(default=None, description="The accumulator for the final result")
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
    _workflow: Optional[Any] = PrivateAttr(default=None)

    @property
    def workflow(self) -> Any:
        return self._workflow

    def clone(self):
        """Creates a deep copy of the context."""
        new_obj = self.model_copy(deep=True)
        new_obj._cursor = self._cursor
        new_obj._jump_to = self._jump_to
        new_obj._workflow = self._workflow
        return new_obj

    def goto(self, step_name: str):
         self._jump_to = step_name
