"""
部门Agent实现
"""
import json
from typing import Dict, Any
from app.agents.base_agent import BaseAgent
from app.models import AgentRole, AgentStatus, ActionType, MessageType, SharedState, Memo, AgentMessage
from app.llm_client import LLMClient


class DepartmentAgent(BaseAgent):
    """部门Agent，代表各个政府部门"""
    
    # 部门配置 + 偏好
    DEPARTMENT_CONFIGS = {
        AgentRole.FINANCE: {
            "name": "财政部",
            "goal": "确保财政可持续性和预算合理性",
            "backstory": "负责财政管理和预算审查，关注政策的财政影响和资金可行性",
            "weights": {
                "financial_cost": 0.5,
                "implementability": 0.3,
                "public_acceptance": 0.1,
                "environmental_benefit": 0.1
            }
        },
        AgentRole.LEGAL: {
            "name": "法制办",
            "goal": "确保政策符合法律法规",
            "backstory": "负责法律审查和合规性检查，确保政策有充分的法律依据",
            "weights": {
                "legal_risk": 0.6,
                "implementability": 0.2,
                "public_acceptance": 0.1,
                "stakeholder_conflict": 0.1
            }
        },
        AgentRole.PLANNING: {
            "name": "规划局",
            "goal": "统筹规划，确保政策与整体规划协调",
            "backstory": "负责城市规划和政策协调，关注政策的长期影响和系统性",
            "weights": {
                "long_term_impact": 0.4,
                "coordination_fit": 0.3,
                "implementability": 0.2,
                "financial_cost": 0.1
            }
        },
        AgentRole.INDUSTRY: {
            "name": "工信局",
            "goal": "促进产业发展和数字化转型",
            "backstory": "负责产业政策制定和执行，关注政策对产业发展的影响",
            "weights": {
                "industry_growth": 0.5,
                "implementability": 0.2,
                "financial_cost": 0.1,
                "public_acceptance": 0.2
            }
        },
        AgentRole.ENVIRONMENT: {
            "name": "环保局",
            "goal": "保护环境和促进可持续发展",
            "backstory": "负责环境保护和生态建设，关注政策的环境影响",
            "weights": {
                "environmental_benefit": 0.6,
                "public_acceptance": 0.2,
                "long_term_impact": 0.1,
                "financial_cost": 0.1
            }
        },
        AgentRole.SECURITY: {
            "name": "安全局",
            "goal": "确保政策实施的安全性和稳定性",
            "backstory": "负责安全风险评估和应急管理，关注政策的安全影响",
            "weights": {
                "security_risk": 0.6,
                "implementability": 0.2,
                "public_acceptance": 0.1,
                "long_term_impact": 0.1
            }
        }
    }

    
    def __init__(self, agent_id: str, role: AgentRole, llm_client: LLMClient):
        config = self.DEPARTMENT_CONFIGS.get(role, {
            "name": role.value,
            "goal": "完成部门职责",
            "backstory": "政府部门",
            "weights": {}
        })
        
        super().__init__(
            agent_id=agent_id,
            role=role,
            llm_client=llm_client,
            name=config["name"],
            goal=config["goal"],
            backstory=config["backstory"],
            weights=config.get("weights", {})
        )
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return f"""
你是{self.name}的负责人。你的职责是：
{self.backstory}

你的目标是：{self.goal}

在决策过程中，你需要：
1. 从{self.name}的角度分析政策提案
2. 提出部门的立场、关切点和建议
3. 与其他部门进行沟通和协调
4. 参与谈判解决分歧
5. 使用工具进行专业分析

请始终以专业、客观的态度参与决策过程。
"""
    
    def _build_thinking_prompt(
        self,
        observations: Dict[str, Any],
        shared_state: SharedState
    ) -> str:
        """构建思考提示词"""
        policy_info = ""
        if shared_state.policy_card:
            policy_info = f"""
政策标题：{shared_state.policy_card.title}
政策摘要：{shared_state.policy_card.summary}
预估预算：{shared_state.policy_card.estimated_budget}元
执行周期：{shared_state.policy_card.duration_months}个月
关键措施：{', '.join(shared_state.policy_card.key_measures)}
"""
        
        return f"""
当前情况：
{policy_info}

议题：{shared_state.issue.title}
描述：{shared_state.issue.description}
当前阶段：{shared_state.current_stage}

你收到了{len(observations.get('pending_messages', []))}条待处理消息。

请思考：
1. 从{self.name}的角度，这个政策提案如何？
2. 有哪些需要关注的方面？
3. 你的立场是什么（支持/反对/有条件支持）？
4. 需要与其他部门沟通什么？
5. 下一步应该做什么？

请给出你的思考和分析。
"""
    
    async def _generate_memo(self, shared_state: SharedState) -> Dict[str, Any]:
        """生成部门备忘录"""
        if not shared_state.policy_card:
            return {"error": "政策卡片不存在"}
        
        prompt = f"""
作为{self.name}的负责人，请对以下政策提案提出部门意见：

政策标题：{shared_state.policy_card.title}
政策摘要：{shared_state.policy_card.summary}
预估预算：{shared_state.policy_card.estimated_budget}元
关键措施：{', '.join(shared_state.policy_card.key_measures)}

请从{self.name}的职责和目标出发，给出【严格 JSON】（不要任何解释文本）：

{{
    "position": "support | oppose | conditional",
    "rationale": "以部门专业视角给出立场理由（不超过250字）",
    "concerns": ["部门最担心的问题1", "部门最担心的问题2"],
    "recommendations": ["希望修改或补充的建议1", "建议2"],
    "conditions": ["在什么条件下可以同意该政策（可妥协点）"],
    "bottom_line": "部门红线（即使谈判也绝不接受的点，务必明确、具体）"
}}

⚠️ 要求：
- 只能输出 JSON
- 字段必须齐全
- 内容必须符合{self.name}的真实职责逻辑
"""
        
        response = self.llm.simple_chat([
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": prompt}
        ])
        
        # 解析备忘录
        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                memo_data = json.loads(response[json_start:json_end])
                memo = Memo(
                    department=self.agent_id,
                    position=memo_data.get("position", "conditional"),
                    rationale=memo_data.get("rationale", ""),
                    concerns=memo_data.get("concerns", []),
                    recommendations=memo_data.get("recommendations", [])
                )
                self.state.conditions = memo_data.get("conditions", [])
                self.state.bottom_line = memo_data.get("bottom_line", "")
            else:
                raise ValueError("未找到JSON格式")
        except Exception:
            # 降级方案
            memo = Memo(
                department=self.agent_id,
                position="conditional",
                rationale=f"{self.name}需要进一步评估该政策",
                concerns=["需要更多信息"],
                recommendations=["加强论证"]
            )
        
        # 更新Agent状态
        self.state.position = memo.position
        self.state.rationale = memo.rationale
        self.state.concerns = memo.concerns
        self.state.recommendations = memo.recommendations
        
        # 添加到共享状态
        shared_state.memos.append(memo)
        
        return {
            "memo": memo.model_dump(),
            "status": "completed"
        }
    
    async def _handle_proposal(
        self,
        message: AgentMessage,
        shared_state: SharedState
    ) -> Dict[str, Any]:
        """处理提案消息：从‘回应’升级为‘谈判反馈’"""

        if not message.from_agent:
            return {"error": "消息发送者不能为空"}

        prompt = f"""
    你是{self.name}，正在参与一项涉及多个政府部门的政策谈判。

    📩 来自部门：{message.from_agent}
    📄 他们的提案内容：
    {message.content}

    🧠 请基于{self.name}的职责、利益与立场，给出【严格 JSON 谈判回应】：
    {{
    "evaluation": "用简短一句话评价该提案（不超过80字）",
    "stance": "accept | accept_with_changes | reject",
    "required_changes": [
        "如果 stance=accept_with_changes：必须修改哪些内容（具体、可操作）"
    ],
    "can_compromise": true | false,
    "compromise_suggestions": [
        "如果可以妥协：你可以给出的折中方案1",
        "折中方案2"
    ],
    "risk_warning": "如果接受当前方案，可能的风险提示（一句话）"
    }}

    ⚠️ 要求
    - 只能输出 JSON
    - 所有 key 必须存在
    - 判断逻辑必须符合{self.name}的真实利益与职责
    """

        response = self.llm.simple_chat([
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": prompt}
        ])

        # 尝试解析 JSON
        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            feedback = json.loads(response[json_start:json_end])
        except Exception:
            feedback = {
                "evaluation": "需要进一步评估该提案",
                "stance": "accept_with_changes",
                "required_changes": ["请补充更多细节与论证"],
                "can_compromise": True,
                "compromise_suggestions": ["可以考虑阶段性推进或试点先行"],
                "risk_warning": "存在财政、执行或风险不确定性"
            }

        # 发送“谈判反馈”而不是普通文本
        reply_text = json.dumps(feedback, ensure_ascii=False, indent=2)

        reply = await self.communicate(
            message.from_agent,
            MessageType.RESPONSE,
            reply_text,
            shared_state
        )

        return {
            "reply_sent": True,
            "message_id": reply.id,
            "negotiation_feedback": feedback
        }
