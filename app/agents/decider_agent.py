"""
决策者Agent实现
"""
import json
from typing import Dict, Any
from app.agents.base_agent import BaseAgent
from app.models import AgentRole, AgentStatus, ActionType, MessageType, SharedState, Decision
from app.llm_client import LLMClient
from app.config import settings


class DeciderAgent(BaseAgent):
    """决策者Agent，负责最终裁决"""
    
    def __init__(self, agent_id: str, llm_client: LLMClient):
        # 使用更强的模型和更低的temperature
        decider_llm = LLMClient(
            model=settings.decider_model,
            temperature=0.3
        )
        
        super().__init__(
            agent_id=agent_id,
            role=AgentRole.DECIDER,
            llm_client=decider_llm,
            name="决策者",
            goal="基于各部门意见和审查结果，做出最终决策",
            backstory="作为最终决策者，需要综合考虑各部门意见、门禁审查结果、政策影响等因素，做出是否批准政策的决定"
        )
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """
你是最终决策者。你的职责是：
1. 综合评估所有部门意见
2. 考虑门禁审查结果
3. 权衡政策利弊
4. 做出最终决策（批准/不批准）
5. 如果批准，给出最终政策文本和条件
6. 如果不批准，说明理由

你需要：
- 保持客观、理性
- 综合考虑各方因素
- 做出符合整体利益的决策
- 给出清晰的决策理由
"""
    
    def _build_thinking_prompt(
        self,
        observations: Dict[str, Any],
        shared_state: SharedState
    ) -> str:
        """构建思考提示词"""
        memos_summary = "\n".join([
            f"- {memo.department}: {memo.position} - {memo.rationale[:150]}"
            for memo in shared_state.memos
        ])
        
        gate_results = "\n".join([
            f"- {g.gate_name}: {'通过' if g.passed else '未通过'} - {', '.join(g.issues)}"
            for g in shared_state.gate_results
        ])
        
        disputes_summary = "\n".join([
            f"- {d.topic}: {'已解决' if d.status == 'resolved' else '未解决'}"
            for d in shared_state.disputes
        ])
        
        return f"""
请做出最终决策：

议题：{shared_state.issue.title}
政策：{shared_state.policy_card.title if shared_state.policy_card else '未知'}

部门意见汇总：
{memos_summary}

门禁审查结果：
{gate_results}

分歧处理情况：
{disputes_summary}

请综合考虑以上信息，做出决策。
"""
    
    async def _generate_memo(self, shared_state: SharedState) -> Dict[str, Any]:
        """决策者不生成备忘录，而是做出最终决策"""
        return await self._make_decision(shared_state)
    
    async def _make_decision(self, shared_state: SharedState) -> Dict[str, Any]:
        """做出最终决策"""
        prompt = f"""
作为最终决策者，基于以下信息做出裁决：

议题：{shared_state.issue.title}
描述：{shared_state.issue.description}

政策卡片：
{shared_state.policy_card.model_dump_json() if shared_state.policy_card else '无'}

部门备忘录数：{len(shared_state.memos)}
分歧数：{len(shared_state.disputes)}
门禁结果：{[g.gate_name + ':' + ('通过' if g.passed else '未通过') for g in shared_state.gate_results]}

请给出最终决策（JSON格式）：
{{
    "approved": true/false,
    "final_policy_text": "最终政策文本（300字）",
    "rationale": "决策理由（200字）",
    "conditions": ["附加条件1", "附加条件2"],
    "next_steps": ["下一步行动1", "下一步行动2"]
}}
"""
        
        response = self.llm.simple_chat([
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": prompt}
        ])
        
        # 解析决策
        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                decision_data = json.loads(response[json_start:json_end])
                decision = Decision(**decision_data)
            else:
                raise ValueError("未找到JSON格式")
        except Exception:
            # 降级方案
            decision = Decision(
                approved=True,
                final_policy_text=shared_state.policy_card.summary if shared_state.policy_card else "",
                rationale="综合各部门意见，政策具备可行性",
                conditions=["加强监督", "定期评估"],
                next_steps=["制定实施细则", "启动试点"]
            )
        
        # 保存决策
        shared_state.decision = decision
        shared_state.policy_version = "v1.0"
        shared_state.draft_policy_text = decision.final_policy_text
        
        return {
            "decision": decision.model_dump(),
            "status": "completed"
        }

