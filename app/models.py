from datetime import datetime
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from enum import Enum


# ===== Enums =====
class AgentRole(str, Enum):
    """Agent角色类型"""
    FINANCE = "finance"
    LEGAL = "legal"
    PLANNING = "planning"
    INDUSTRY = "industry"
    ENVIRONMENT = "environment"
    SECURITY = "security"
    OFFICE = "office"  # 办公厅
    DECIDER = "decider"  # 决策者


class AgentStatus(str, Enum):
    """Agent状态"""
    IDLE = "idle"
    OBSERVING = "observing"
    THINKING = "thinking"
    ACTING = "acting"
    PLANNING = "planning"
    COMMUNICATING = "communicating"
    WAITING = "waiting"


class MessageType(str, Enum):
    """消息类型"""
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    QUERY = "query"
    PROPOSAL = "proposal"
    AGREEMENT = "agreement"
    DISAGREEMENT = "disagreement"


class ActionType(str, Enum):
    """行动类型"""
    GENERATE_MEMO = "generate_memo"
    SEND_MESSAGE = "send_message"
    REQUEST_INFO = "request_info"
    PROPOSE_SOLUTION = "propose_solution"
    NEGOTIATE = "negotiate"
    REVIEW = "review"
    DECIDE = "decide"
    USE_TOOL = "use_tool"


# ===== Issue =====
class Issue(BaseModel):
    id: str
    title: str
    description: str
    background: str
    urgency: Literal["low", "medium", "high", "critical"]
    sectors: List[str] = Field(default_factory=list)


# ===== Policy Card =====
class PolicyCard(BaseModel):
    title: str
    summary: str
    estimated_budget: float = 0.0
    duration_months: int = 12
    affected_population: int = 0
    key_measures: List[str] = Field(default_factory=list)
    risk_factors: List[str] = Field(default_factory=list)


# ===== Constraints =====
class Constraints(BaseModel):
    budget_ceiling: float = 1e9
    legal_requirements: List[str] = Field(default_factory=list)
    timeline_deadline: Optional[str] = None
    stakeholder_priorities: Dict[str, str] = Field(default_factory=dict)


# ===== Agent Message =====
class AgentMessage(BaseModel):
    """Agent间通信消息"""
    id: str
    from_agent: str
    to_agent: str
    message_type: MessageType
    content: str
    context: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    requires_response: bool = False
    responded: bool = False


# ===== Agent Plan =====
class PlanStep(BaseModel):
    """规划步骤"""
    step_id: str
    description: str
    action_type: ActionType
    dependencies: List[str] = Field(default_factory=list)  # 依赖的其他步骤ID
    status: Literal["pending", "in_progress", "completed", "failed"] = "pending"
    result: Optional[str] = None


class AgentPlan(BaseModel):
    """Agent的局部规划"""
    agent_id: str
    goal: str
    steps: List[PlanStep] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    is_active: bool = True


# ===== Agent Memory =====
class AgentMemory(BaseModel):
    """Agent的短期记忆"""
    agent_id: str
    observations: List[str] = Field(default_factory=list)  # 观察记录
    thoughts: List[str] = Field(default_factory=list)  # 思考记录
    actions: List[Dict[str, Any]] = Field(default_factory=list)  # 行动记录
    received_messages: List[AgentMessage] = Field(default_factory=list)  # 收到的消息
    sent_messages: List[AgentMessage] = Field(default_factory=list)  # 发送的消息
    last_updated: datetime = Field(default_factory=datetime.now)


# ===== Agent State =====
class AgentState(BaseModel):
    """单个Agent的状态"""
    agent_id: str
    role: AgentRole
    status: AgentStatus = AgentStatus.IDLE
    current_task: Optional[str] = None
    plan: Optional[AgentPlan] = None
    memory: AgentMemory
    position: Optional[str] = None  # support / oppose / conditional
    rationale: Optional[str] = None
    concerns: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    last_action: Optional[Dict[str, Any]] = None
    last_updated: datetime = Field(default_factory=datetime.now)


# ===== Memo =====
class Memo(BaseModel):
    department: str
    position: str  # support / oppose / conditional
    rationale: str
    concerns: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)


# ===== Dispute =====
class Dispute(BaseModel):
    id: str
    departments: List[str]
    topic: str
    positions: Dict[str, str] = Field(default_factory=dict)
    severity: Literal["low", "medium", "high"]
    status: Literal["unresolved", "negotiating", "resolved"] = "unresolved"
    resolution: Optional[str] = None


# ===== Negotiation Round =====
class NegotiationRound(BaseModel):
    round_number: int
    disputes_addressed: List[str] = Field(default_factory=list)
    resolutions: Dict[str, str] = Field(default_factory=dict)
    remaining_disputes: List[str] = Field(default_factory=list)
    convergence_score: float = 1.0
    timestamp: datetime = Field(default_factory=datetime.now)


# ===== Gate Result =====
class GateResult(BaseModel):
    gate_name: str
    passed: bool
    issues: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)


# ===== Decision =====
class Decision(BaseModel):
    approved: bool
    final_policy_text: str
    rationale: str
    conditions: List[str] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)


# ===== Trace Event =====
class TraceEvent(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now)
    stage: str
    event_type: str
    message: str
    agent_id: Optional[str] = None  # 新增：关联的Agent
    data: Optional[Dict[str, Any]] = None


# ===== Artifact =====
class Artifact(BaseModel):
    name: str
    type: str
    path: str
    size_bytes: int = 0
    created_at: datetime = Field(default_factory=datetime.now)


# ===== Shared State (Multi-Agent) =====
class SharedState(BaseModel):
    """多Agent共享状态"""
    # Core
    run_id: str
    issue: Issue
    constraints: Constraints
    
    # Policy Evolution
    draft_policy_text: str = ""
    policy_version: str = "v0.0"
    policy_card: Optional[PolicyCard] = None
    
    # Agent States
    agents: Dict[str, AgentState] = Field(default_factory=dict)  # agent_id -> AgentState
    
    # Communication
    message_queue: List[AgentMessage] = Field(default_factory=list)  # 消息队列
    
    # Workflow Data (保留兼容性)
    memos: List[Memo] = Field(default_factory=list)
    disputes: List[Dispute] = Field(default_factory=list)
    negotiation_history: List[NegotiationRound] = Field(default_factory=list)
    gate_results: List[GateResult] = Field(default_factory=list)
    decision: Optional[Decision] = None
    
    # Run Status
    run_status: Literal["pending", "running", "completed", "failed"] = "pending"
    current_stage: str = "init"
    error_message: Optional[str] = None
    
    # Tracing & Artifacts
    trace_log: List[TraceEvent] = Field(default_factory=list)
    artifacts_index: List[Artifact] = Field(default_factory=list)
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# ===== Run Config =====
class RunConfig(BaseModel):
    issue_id: Optional[str] = None
    custom_issue: Optional[Issue] = None
    max_rounds: int = 5
    convergence_threshold: float = 0.15
    model: str = "qwen-plus"
    temperature: float = 0.7
    enable_search: bool = False
    enable_public_opinion: bool = False
