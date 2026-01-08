"""
基础Agent类，实现观察-思考-行动循环
"""
import uuid
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from abc import ABC, abstractmethod

from app.models import (
    AgentRole, AgentStatus, AgentState, AgentMemory, AgentPlan, PlanStep,
    AgentMessage, MessageType, ActionType, SharedState
)
from app.llm_client import LLMClient
from app.tools import execute_tool, TOOL_SCHEMAS


class BaseAgent(ABC):
    """基础Agent类，实现观察-思考-行动循环"""
    
    def __init__(
        self,
        agent_id: str,
        role: AgentRole,
        llm_client: LLMClient,
        name: str = "",
        goal: str = "",
        backstory: str = ""
    ):
        self.agent_id = agent_id
        self.role = role
        self.llm = llm_client
        self.name = name or role.value
        self.goal = goal
        self.backstory = backstory
        
        # 初始化状态
        self.state = AgentState(
            agent_id=agent_id,
            role=role,
            status=AgentStatus.IDLE,
            memory=AgentMemory(agent_id=agent_id)
        )
    
    async def observe(self, shared_state: SharedState) -> Dict[str, Any]:
        """
        观察阶段：感知环境信息
        返回观察结果
        """
        self.state.status = AgentStatus.OBSERVING
        
        observations = {
            "policy_card": shared_state.policy_card.model_dump() if shared_state.policy_card else None,
            "issue": shared_state.issue.model_dump(),
            "constraints": shared_state.constraints.model_dump(),
            "other_agents_status": {
                agent_id: agent.status for agent_id, agent in shared_state.agents.items()
                if agent_id != self.agent_id
            },
            "pending_messages": [
                msg.model_dump() for msg in shared_state.message_queue
                if msg.to_agent == self.agent_id and not msg.responded
            ],
            "disputes": [d.model_dump() for d in shared_state.disputes],
            "current_stage": shared_state.current_stage
        }
        
        # 记录观察
        self.state.memory.observations.append(
            f"[{datetime.now()}] 观察到环境状态：阶段={shared_state.current_stage}"
        )
        
        return observations
    
    async def think(
        self,
        observations: Dict[str, Any],
        shared_state: SharedState
    ) -> Dict[str, Any]:
        """
        思考阶段：基于观察进行推理和规划
        返回思考结果和下一步计划
        """
        self.state.status = AgentStatus.THINKING
        
        # 构建思考提示
        prompt = self._build_thinking_prompt(observations, shared_state)
        
        # 调用LLM进行思考
        response = self.llm.simple_chat([
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": prompt}
        ])
        
        # 解析思考结果
        thinking_result = self._parse_thinking(response)
        
        # 记录思考
        self.state.memory.thoughts.append(
            f"[{datetime.now()}] {thinking_result.get('summary', '进行思考')}"
        )
        
        return thinking_result
    
    async def plan(
        self,
        goal: str,
        context: Dict[str, Any],
        shared_state: SharedState
    ) -> AgentPlan:
        """
        规划阶段：生成局部规划（根据当前阶段自主决策）
        """
        self.state.status = AgentStatus.PLANNING
        
        # 根据当前阶段决定应该做什么
        current_stage = shared_state.current_stage
        stage_hints = {
            "departments_generate_memos": "你需要生成部门备忘录，分析政策提案并提出部门意见。第一步应该使用 action_type: 'generate_memo'",
            "secretariat_aggregate_disputes": "你需要汇总各部门的分歧点。第一步应该使用 action_type: 'generate_memo'（办公厅的generate_memo会汇总分歧）",
            "negotiation_rounds": "你需要协调分歧，组织谈判。可以使用 action_type: 'negotiate' 或 'propose_solution'",
            "legal_review_gate": "你需要进行法律审查，检查政策合规性。第一步应该使用 action_type: 'review'",
            "fiscal_capacity_review_gate": "你需要进行财政审查，评估财政可行性。第一步应该使用 action_type: 'review'",
            "decider_finalize": "你需要做出最终决策。第一步应该使用 action_type: 'generate_memo'（决策者的generate_memo会做出决策）",
        }
        
        stage_hint = stage_hints.get(current_stage, "根据当前情况完成你的任务")
        
        # 构建规划提示
        prompt = f"""
作为{self.name}，你的目标是：{goal}

当前环境：
- 政策：{context.get('policy_title', shared_state.policy_card.title if shared_state.policy_card else '未知')}
- 当前阶段：{current_stage}
- 阶段任务：{stage_hint}
- 其他Agent状态：{context.get('other_agents_status', {})}

请根据当前阶段和你的职责，制定一个执行计划，包含2-4个步骤。每个步骤应该：
1. 有明确的描述
2. 说明需要执行什么行动（action_type可以是：generate_memo, send_message, request_info, propose_solution, negotiate, review, decide, use_tool）
3. 如果有依赖关系，说明依赖哪些步骤

请以JSON格式输出：
{{
    "goal": "目标描述",
    "steps": [
        {{
            "step_id": "step_1",
            "description": "步骤描述",
            "action_type": "行动类型",
            "dependencies": []
        }}
    ]
}}
"""
        
        response = self.llm.simple_chat([
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": prompt}
        ])
        
        # 解析规划
        plan = self._parse_plan(response, goal)
        self.state.plan = plan
        
        return plan
    
    async def act(
        self,
        action: Dict[str, Any],
        shared_state: SharedState
    ) -> Dict[str, Any]:
        """
        行动阶段：执行具体行动
        """
        self.state.status = AgentStatus.ACTING
        self.state.current_task = action.get("description", "")
        
        action_type = action.get("action_type")
        # 如果 action_type 是字符串，转换为枚举
        if isinstance(action_type, str):
            try:
                action_type = ActionType(action_type)
            except ValueError:
                return {"error": f"未知行动类型: {action_type}"}
        
        if not action_type:
            return {"error": "action_type 不能为空"}
        
        result = {}
        
        if action_type == ActionType.GENERATE_MEMO:
            result = await self._generate_memo(shared_state)
        elif action_type == ActionType.SEND_MESSAGE:
            result = await self._send_message(action, shared_state)
        elif action_type == ActionType.REQUEST_INFO:
            result = await self._request_info(action, shared_state)
        elif action_type == ActionType.PROPOSE_SOLUTION:
            result = await self._propose_solution(action, shared_state)
        elif action_type == ActionType.NEGOTIATE:
            result = await self._negotiate(action, shared_state)
        elif action_type == ActionType.REVIEW:
            result = await self._review(action, shared_state)
        elif action_type == ActionType.DECIDE:
            result = await self._decide(action, shared_state)
        elif action_type == ActionType.USE_TOOL:
            result = await self._use_tool(action, shared_state)
        else:
            result = {"error": f"未知行动类型: {action_type}"}
        
        # 记录行动
        self.state.memory.actions.append({
            "timestamp": datetime.now().isoformat(),
            "action_type": action_type,
            "result": result
        })
        self.state.last_action = {
            "action_type": action_type,
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
        
        return result
    
    async def communicate(
        self,
        to_agent: str,
        message_type: MessageType,
        content: str,
        shared_state: SharedState,
        context: Optional[Dict[str, Any]] = None
    ) -> AgentMessage:
        """
        与其他Agent通信
        """
        if not to_agent:
            raise ValueError("to_agent 不能为空或 None")
        
        self.state.status = AgentStatus.COMMUNICATING
        
        message = AgentMessage(
            id=str(uuid.uuid4()),
            from_agent=self.agent_id,
            to_agent=to_agent,
            message_type=message_type,
            content=content,
            context=context or {},
            requires_response=message_type in [MessageType.REQUEST, MessageType.QUERY]
        )
        
        # 添加到消息队列
        shared_state.message_queue.append(message)
        
        # 记录到记忆
        self.state.memory.sent_messages.append(message)
        
        return message
    
    async def process_message(
        self,
        message: AgentMessage,
        shared_state: SharedState
    ) -> Optional[AgentMessage]:
        """
        处理收到的消息
        """
        # 记录到记忆
        self.state.memory.received_messages.append(message)
        message.responded = True
        
        # 根据消息类型处理
        if message.message_type == MessageType.REQUEST:
            return await self._handle_request(message, shared_state)
        elif message.message_type == MessageType.QUERY:
            return await self._handle_query(message, shared_state)
        elif message.message_type == MessageType.PROPOSAL:
            return await self._handle_proposal(message, shared_state)
        
        return None
    
    async def update_plan(
        self,
        shared_state: SharedState,
        reason: str
    ) -> AgentPlan:
        """
        动态调整规划
        """
        if not self.state.plan:
            # 如果没有规划，创建新规划
            goal = self.goal or f"完成{self.name}的任务"
            context = await self.observe(shared_state)
            return await self.plan(goal, context, shared_state)
        
        # 调整现有规划
        prompt = f"""
当前规划：
{self.state.plan.model_dump_json()}

需要调整的原因：{reason}

当前环境状态：
- 阶段：{shared_state.current_stage}
- 政策：{shared_state.policy_card.title if shared_state.policy_card else '未知'}

请更新规划，可能需要：
1. 修改未完成的步骤
2. 添加新步骤
3. 删除不再需要的步骤

请以JSON格式输出更新后的规划。
"""
        
        response = self.llm.simple_chat([
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": prompt}
        ])
        
        updated_plan = self._parse_plan(response, self.state.plan.goal)
        updated_plan.updated_at = datetime.now()
        self.state.plan = updated_plan
        
        return updated_plan
    
    # ===== 抽象方法，子类需要实现 =====
    
    @abstractmethod
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        pass
    
    @abstractmethod
    def _build_thinking_prompt(
        self,
        observations: Dict[str, Any],
        shared_state: SharedState
    ) -> str:
        """构建思考提示词"""
        pass
    
    @abstractmethod
    async def _generate_memo(self, shared_state: SharedState) -> Dict[str, Any]:
        """生成备忘录（部门Agent需要实现）"""
        pass
    
    # ===== 默认实现的方法 =====
    
    def _parse_thinking(self, response: str) -> Dict[str, Any]:
        """解析思考结果"""
        # 简单实现，可以改进
        return {
            "summary": response[:200],
            "reasoning": response,
            "next_action": "continue"
        }
    
    def _parse_plan(self, response: str, goal: str) -> AgentPlan:
        """解析规划结果"""
        import json
        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                plan_data = json.loads(response[json_start:json_end])
                steps = [
                    PlanStep(**step) for step in plan_data.get("steps", [])
                ]
                return AgentPlan(
                    agent_id=self.agent_id,
                    goal=plan_data.get("goal", goal),
                    steps=steps
                )
        except Exception as e:
            pass
        
        # 降级方案：创建简单规划
        return AgentPlan(
            agent_id=self.agent_id,
            goal=goal,
            steps=[
                PlanStep(
                    step_id="step_1",
                    description="执行主要任务",
                    action_type=ActionType.GENERATE_MEMO
                )
            ]
        )
    
    async def _send_message(
        self,
        action: Dict[str, Any],
        shared_state: SharedState
    ) -> Dict[str, Any]:
        """发送消息"""
        to_agent = action.get("to_agent")
        if not to_agent:
            return {"error": "to_agent 不能为空"}
        
        content = action.get("content", "")
        message_type = MessageType(action.get("message_type", "notification"))
        
        message = await self.communicate(to_agent, message_type, content, shared_state)
        return {"message_id": message.id, "status": "sent"}
    
    async def _request_info(
        self,
        action: Dict[str, Any],
        shared_state: SharedState
    ) -> Dict[str, Any]:
        """请求信息"""
        to_agent = action.get("to_agent")
        if not to_agent:
            return {"error": "to_agent 不能为空"}
        
        query = action.get("query", "")
        
        message = await self.communicate(
            to_agent,
            MessageType.QUERY,
            query,
            shared_state
        )
        return {"message_id": message.id, "status": "requested"}
    
    async def _propose_solution(
        self,
        action: Dict[str, Any],
        shared_state: SharedState
    ) -> Dict[str, Any]:
        """提出解决方案"""
        to_agent = action.get("to_agent")
        if not to_agent:
            return {"error": "to_agent 不能为空"}
        
        proposal = action.get("proposal", "")
        
        message = await self.communicate(
            to_agent,
            MessageType.PROPOSAL,
            proposal,
            shared_state
        )
        return {"message_id": message.id, "status": "proposed"}
    
    async def _negotiate(
        self,
        action: Dict[str, Any],
        shared_state: SharedState
    ) -> Dict[str, Any]:
        """谈判"""
        dispute_id = action.get("dispute_id")
        proposal = action.get("proposal", "")
        
        # 找到相关分歧
        dispute = next((d for d in shared_state.disputes if d.id == dispute_id), None)
        if not dispute:
            return {"error": "分歧未找到"}
        
        # 发送提案给相关部门
        results = []
        for dept in dispute.departments:
            if dept and dept != self.agent_id:
                message = await self.communicate(
                    dept,
                    MessageType.PROPOSAL,
                    proposal,
                    shared_state,
                    {"dispute_id": dispute_id}
                )
                results.append({"to": dept, "message_id": message.id})
        
        return {"status": "negotiating", "messages": results}
    
    async def _review(
        self,
        action: Dict[str, Any],
        shared_state: SharedState
    ) -> Dict[str, Any]:
        """审查"""
        review_type = action.get("review_type", "general")
        result = {"review_type": review_type, "passed": True, "issues": []}
        return result
    
    async def _decide(
        self,
        action: Dict[str, Any],
        shared_state: SharedState
    ) -> Dict[str, Any]:
        """决策"""
        decision = action.get("decision", {})
        return {"status": "decided", "decision": decision}
    
    async def _use_tool(
        self,
        action: Dict[str, Any],
        shared_state: SharedState
    ) -> Dict[str, Any]:
        """使用工具"""
        tool_name = action.get("tool_name")
        arguments = action.get("arguments", {})
        
        # 如果缺少policy_card，从shared_state获取
        if "policy_card" not in arguments and shared_state.policy_card:
            arguments["policy_card"] = shared_state.policy_card.model_dump()
        
        result = execute_tool(tool_name, arguments)
        return {"tool": tool_name, "result": result}
    
    async def _handle_request(
        self,
        message: AgentMessage,
        shared_state: SharedState
    ) -> Optional[AgentMessage]:
        """处理请求消息"""
        if not message.from_agent:
            return None
        
        # 默认实现：简单回复
        response_content = f"收到来自{message.from_agent}的请求：{message.content}"
        return await self.communicate(
            message.from_agent,
            MessageType.RESPONSE,
            response_content,
            shared_state
        )
    
    async def _handle_query(
        self,
        message: AgentMessage,
        shared_state: SharedState
    ) -> Optional[AgentMessage]:
        """处理查询消息"""
        if not message.from_agent:
            return None
        
        # 默认实现：简单回复
        response_content = f"关于'{message.content}'的回复：需要进一步分析"
        return await self.communicate(
            message.from_agent,
            MessageType.RESPONSE,
            response_content,
            shared_state
        )
    
    async def _handle_proposal(
        self,
        message: AgentMessage,
        shared_state: SharedState
    ) -> Optional[AgentMessage]:
        """处理提案消息"""
        if not message.from_agent:
            return None
        
        # 默认实现：简单回复
        response_content = f"收到来自{message.from_agent}的提案，需要评估"
        return await self.communicate(
            message.from_agent,
            MessageType.RESPONSE,
            response_content,
            shared_state
        )
    
    def get_state(self) -> AgentState:
        """获取当前状态"""
        self.state.last_updated = datetime.now()
        return self.state
    
    def update_state(self, **kwargs):
        """更新状态"""
        for key, value in kwargs.items():
            if hasattr(self.state, key):
                setattr(self.state, key, value)
        self.state.last_updated = datetime.now()

