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


from typing import Any, Dict, Optional
from dataclasses import dataclass, field
import copy

@dataclass
class ExecContext:
    # 1. El Payload: Los datos de negocio que se transforman
    data: Any
    
    # 2. Control de Flujo: Flags para el motor
    jump_to: Optional[str] = None
    stop: bool = False
    
    # 3. Bus de Infraestructura: Aquí vive TODO lo demás
    # - shared_data['metadata']: Trazabilidad, logs, IDs
    # - shared_data['cleanup']: El CleanupManager
    # - shared_data['auth']: Tokens o info de sesión
    shared_data: Dict[str, Any] = field(default_factory=dict)

