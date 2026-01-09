from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime


class NegotiationRound(BaseModel):
    round_id: int
    issue_id: str
    
    # 各部门提案（例如 数值/枚举）
    proposals: Dict[str, Any] = {}

    # 冲突分析
    conflict_dimension: Optional[str] = None
    conflict_level: Optional[float] = None  # 0~1
    
    # 状态
    status: str = "running"  # running / resolved / failed
    
    # 历史记录（每轮争论 / 让步 / 理由）
    history: List[Dict[str, Any]] = []

    created_at: datetime = datetime.now()


class NegotiationState(BaseModel):
    issue_id: str
    
    rounds: List[NegotiationRound] = []
    
    compromise: Optional[Dict[str, Any]] = None  
    resolved: bool = False
    resolved_at: Optional[datetime] = None
