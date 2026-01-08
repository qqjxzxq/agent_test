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
    
    # 部门配置
    DEPARTMENT_CONFIGS = {
        AgentRole.FINANCE: {
            "name": "财政部",
            "goal": "确保财政可持续性和预算合理性",
            "backstory": "负责财政管理和预算审查，关注政策的财政影响和资金可行性"
        },
        AgentRole.LEGAL: {
            "name": "法制办",
            "goal": "确保政策符合法律法规",
            "backstory": "负责法律审查和合规性检查，确保政策有充分的法律依据"
        },
        AgentRole.PLANNING: {
            "name": "规划局",
            "goal": "统筹规划，确保政策与整体规划协调",
            "backstory": "负责城市规划和政策协调，关注政策的长期影响和系统性"
        },
        AgentRole.INDUSTRY: {
            "name": "工信局",
            "goal": "促进产业发展和数字化转型",
            "backstory": "负责产业政策制定和执行，关注政策对产业发展的影响"
        },
        AgentRole.ENVIRONMENT: {
            "name": "环保局",
            "goal": "保护环境和促进可持续发展",
            "backstory": "负责环境保护和生态建设，关注政策的环境影响"
        },
        AgentRole.SECURITY: {
            "name": "安全局",
            "goal": "确保政策实施的安全性和稳定性",
            "backstory": "负责安全风险评估和应急管理，关注政策的安全影响"
        }
    }
    
    def __init__(self, agent_id: str, role: AgentRole, llm_client: LLMClient):
        config = self.DEPARTMENT_CONFIGS.get(role, {
            "name": role.value,
            "goal": "完成部门职责",
            "backstory": "政府部门"
        })
        
        super().__init__(
            agent_id=agent_id,
            role=role,
            llm_client=llm_client,
            name=config["name"],
            goal=config["goal"],
            backstory=config["backstory"]
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

请从{self.name}的职责和目标出发，给出详细的备忘录（JSON格式）：
{{
    "position": "support/oppose/conditional",
    "rationale": "立场理由（200字）",
    "concerns": ["关切点1", "关切点2"],
    "recommendations": ["建议1", "建议2"],
    "conditions": ["在什么条件下支持"],
    "bottom_line": "部门红线（不能接受什么）"
}}
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
        """处理提案消息（部门Agent可以参与谈判）"""
        if not message.from_agent:
            return {"error": "消息发送者不能为空"}
        
        # 分析提案
        prompt = f"""
收到来自{message.from_agent}的提案：
{message.content}

请评估这个提案：
1. 是否符合{self.name}的利益和立场？
2. 是否可以接受？
3. 需要什么修改？

请给出你的评估和回复。
"""
        
        response = self.llm.simple_chat([
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": prompt}
        ])
        
        # 发送回复
        reply = await self.communicate(
            message.from_agent,
            MessageType.RESPONSE,
            response,
            shared_state
        )
        
        return {"reply_sent": True, "message_id": reply.id}

