from typing import Any, Dict, Optional, List, Tuple
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from typing import Callable, Awaitable, TypeAlias, Union, AsyncGenerator

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


@dataclass
class ExecContext:
    # 1. The Payload: Business data that is transformed
    data: Any = None
    
    # 2. Flow Control: Flags for sequential workflow
    jump_to: Optional[str] = None
    stop: bool = False
    
    # 3. Infrastructure Bus: Here lives everything else
    # - shared_data['metadata']: Traceability, logs, IDs
    # - shared_data['cleanup']: The CleanupManager
    # - shared_data['auth']: Tokens or session info
    shared_data: Dict[str, Any] = field(default_factory=dict)

Middleware: TypeAlias = Callable[
    [ExecContext],
    Union[ExecContext, Awaitable[ExecContext]]
]

StreamHandler: TypeAlias = Callable[
    [Any, ExecContext],
    Union[
        Any,
        Awaitable[Any],
        AsyncGenerator[Any, None]
    ]
]

Transform = Callable[
    [AsyncGenerator[Any, None], ExecContext],
    AsyncGenerator[Any, None]
]