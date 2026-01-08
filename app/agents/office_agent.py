"""
办公厅Agent实现（协调者）
"""
import json
from typing import Dict, Any, List
from app.agents.base_agent import BaseAgent
from app.models import (
    AgentRole, AgentStatus, ActionType, MessageType, SharedState,
    Dispute, NegotiationRound, AgentMessage
)
from app.llm_client import LLMClient


class OfficeAgent(BaseAgent):
    """办公厅Agent，负责协调各部门"""
    
    def __init__(self, agent_id: str, llm_client: LLMClient):
        super().__init__(
            agent_id=agent_id,
            role=AgentRole.OFFICE,
            llm_client=llm_client,
            name="办公厅",
            goal="协调各部门，汇总分歧，促进共识达成",
            backstory="办公厅负责协调各部门工作，汇总各方意见，识别分歧，组织谈判，推动决策进程"
        )
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """
你是办公厅的协调者。你的职责是：
1. 汇总各部门的备忘录和意见
2. 识别部门间的分歧点
3. 组织协调和谈判
4. 推动决策进程
5. 确保信息在各部门间有效传递

你需要保持中立、客观，以促进共识为目标。
"""
    
    def _build_thinking_prompt(
        self,
        observations: Dict[str, Any],
        shared_state: SharedState
    ) -> str:
        """构建思考提示词"""
        memos_summary = "\n".join([
            f"- {memo.department}: {memo.position} - {memo.rationale[:100]}"
            for memo in shared_state.memos
        ])
        
        disputes_summary = "\n".join([
            f"- {d.topic}: 涉及{departments}，严重度{d.severity}"
            for d in shared_state.disputes
            for departments in [', '.join(d.departments)]
        ])
        
        return f"""
当前情况：
- 已收到{len(shared_state.memos)}份部门备忘录
- 识别到{len(shared_state.disputes)}个分歧点
- 当前阶段：{shared_state.current_stage}

部门备忘录摘要：
{memos_summary}

分歧点：
{disputes_summary}

请思考：
1. 当前有哪些需要协调的事项？
2. 哪些分歧需要优先处理？
3. 如何组织谈判？
4. 下一步应该做什么？
"""
    
    async def _generate_memo(self, shared_state: SharedState) -> Dict[str, Any]:
        """办公厅不生成备忘录，而是汇总分歧"""
        return await self._aggregate_disputes(shared_state)
    
    async def _aggregate_disputes(self, shared_state: SharedState) -> Dict[str, Any]:
        """汇总分歧"""
        if len(shared_state.memos) == 0:
            return {"error": "还没有部门备忘录"}
        
        # 如果已经汇总过分歧，避免重复创建
        if len(shared_state.disputes) > 0:
            # 检查是否已经有相同主题的分歧
            existing_topics = {d.topic for d in shared_state.disputes}
            if "预算与执行细节" in existing_topics or "政策必要性与可行性" in existing_topics:
                return {
                    "disputes_identified": len(shared_state.disputes),
                    "disputes": [d.model_dump() for d in shared_state.disputes],
                    "status": "already_aggregated"
                }
        
        # 分析部门立场
        positions = {}
        for memo in shared_state.memos:
            positions[memo.department] = memo.position
        
        # 识别分歧
        oppose_depts = [d for d, p in positions.items() if p == "oppose"]
        conditional_depts = [d for d, p in positions.items() if p == "conditional"]
        support_depts = [d for d, p in positions.items() if p == "support"]
        
        disputes = []
        
        # 如果有反对部门，创建高严重度分歧
        if oppose_depts:
            dispute = Dispute(
                id=f"dispute_{len(shared_state.disputes) + len(disputes) + 1}",
                departments=oppose_depts + (support_depts[:1] if support_depts else []),
                topic="政策必要性与可行性",
                positions={d: "反对" for d in oppose_depts},
                severity="high"
            )
            disputes.append(dispute)
            shared_state.disputes.append(dispute)
        
        # 如果有条件支持部门，创建中严重度分歧（只创建一个，包含所有条件支持部门）
        if conditional_depts:
            dispute = Dispute(
                id=f"dispute_{len(shared_state.disputes) + len(disputes) + 1}",
                departments=conditional_depts,
                topic="预算与执行细节",
                positions={d: "有条件支持" for d in conditional_depts},
                severity="medium"
            )
            disputes.append(dispute)
            shared_state.disputes.append(dispute)
        
        # 如果所有部门都支持，创建一个低严重度的"执行细节"分歧，确保有谈判内容
        if not disputes and support_depts:
            # 选择前两个部门作为代表（如果有多个部门）
            selected_depts = support_depts[:2] if len(support_depts) >= 2 else support_depts
            dispute = Dispute(
                id=f"dispute_{len(shared_state.disputes) + len(disputes) + 1}",
                departments=selected_depts,
                topic="政策执行细节与时间安排",
                positions={d: "支持" for d in selected_depts},
                severity="low"
            )
            disputes.append(dispute)
            shared_state.disputes.append(dispute)
        
        return {
            "disputes_identified": len(disputes),
            "disputes": [d.model_dump() for d in disputes],
            "status": "completed"
        }
    
    async def _organize_negotiation(
        self,
        dispute: Dispute,
        shared_state: SharedState
    ) -> Dict[str, Any]:
        """组织谈判"""
        # 构建谈判提示
        prompt = f"""
作为协调者，请协调以下分歧：

分歧主题：{dispute.topic}
涉及部门：{', '.join(dispute.departments)}
各方立场：{json.dumps(dispute.positions, ensure_ascii=False)}

请提出一个调解方案，帮助各方达成共识。方案应该：
1. 考虑各方的关切
2. 提出可行的妥协方案
3. 明确各方需要做出的调整

请给出调解方案（100字内）。
"""
        
        resolution = self.llm.simple_chat([
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": prompt}
        ])
        
        # 更新分歧状态
        dispute.status = "resolved"
        dispute.resolution = resolution[:200]
        
        return {
            "dispute_id": dispute.id,
            "resolution": resolution,
            "status": "resolved"
        }
    
    async def _handle_proposal(
        self,
        message: AgentMessage,
        shared_state: SharedState
    ) -> Dict[str, Any]:
        """处理提案（办公厅可以转发给相关部门）"""
        # 办公厅通常不直接处理提案，而是转发
        return {"status": "forwarded"}

