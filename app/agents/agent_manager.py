"""
Agent管理器，负责Agent的创建、协调和通信
"""
import uuid
import asyncio
from typing import Dict, List, Optional
from app.models import AgentRole, SharedState, AgentMessage, MessageType, ActionType, PlanStep, AgentPlan
from app.agents.base_agent import BaseAgent
from app.agents.department_agent import DepartmentAgent
from app.agents.office_agent import OfficeAgent
from app.agents.decider_agent import DeciderAgent
from app.llm_client import LLMClient


class AgentManager:
    """Agent管理器"""
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        self.agents: Dict[str, BaseAgent] = {}
        self.agent_roles: Dict[str, AgentRole] = {}
    
    def create_agents(self) -> Dict[str, BaseAgent]:
        """创建所有Agent"""
        agents = {}
        
        # 创建部门Agent
        department_roles = [
            AgentRole.FINANCE,
            AgentRole.LEGAL,
            AgentRole.PLANNING,
            AgentRole.INDUSTRY,
            AgentRole.ENVIRONMENT,
            AgentRole.SECURITY
        ]
        
        for role in department_roles:
            agent_id = f"agent_{role.value}"
            agent = DepartmentAgent(agent_id, role, self.llm)
            agents[agent_id] = agent
            self.agent_roles[agent_id] = role
        
        # 创建办公厅Agent
        office_id = "agent_office"
        office_agent = OfficeAgent(office_id, self.llm)
        agents[office_id] = office_agent
        self.agent_roles[office_id] = AgentRole.OFFICE
        
        # 创建决策者Agent
        decider_id = "agent_decider"
        decider_agent = DeciderAgent(decider_id, self.llm)
        agents[decider_id] = decider_agent
        self.agent_roles[decider_id] = AgentRole.DECIDER
        
        self.agents = agents
        return agents
    
    async def process_messages(self, shared_state: SharedState):
        """处理消息队列"""
        # 处理未响应的消息
        unprocessed = [
            msg for msg in shared_state.message_queue
            if not msg.responded and msg.to_agent and msg.to_agent in self.agents
        ]
        
        for message in unprocessed:
            if message.to_agent in self.agents:
                agent = self.agents[message.to_agent]
                await agent.process_message(message, shared_state)
    
    async def run_agent_cycle(
        self,
        agent_id: str,
        shared_state: SharedState
    ) -> Dict:
        """
        运行单个Agent的一个观察-思考-行动循环
        """
        agent = self.agents.get(agent_id)
        if not agent:
            return {"error": f"Agent {agent_id} not found"}
        
        # 1. 观察
        observations = await agent.observe(shared_state)
        
        # 2. 处理消息
        await self.process_messages(shared_state)
        
        # 3. 思考
        thinking_result = await agent.think(observations, shared_state)
        
        # 4. 检查是否需要规划
        if not agent.state.plan or not agent.state.plan.is_active:
            goal = agent.goal or f"完成{agent.name}的任务"
            plan = await agent.plan(goal, observations, shared_state)
            agent.state.plan = plan  # 更新Agent的规划
        else:
            plan = agent.state.plan
        
        # 确保规划存在且有步骤，如果没有则创建默认规划
        if not plan or not plan.steps:
            # 根据当前阶段和Agent角色创建默认规划
            current_stage = shared_state.current_stage
            
            # 确定默认行动类型
            default_action_type = ActionType.GENERATE_MEMO  # 默认行动
            if current_stage == "secretariat_aggregate_disputes" and agent.role.value == "office":
                default_action_type = ActionType.GENERATE_MEMO  # 办公厅的generate_memo会汇总分歧
            elif current_stage == "decider_finalize" and agent.role.value == "decider":
                default_action_type = ActionType.GENERATE_MEMO  # 决策者的generate_memo会做出决策
            elif current_stage in ["legal_review_gate", "fiscal_capacity_review_gate"]:
                default_action_type = ActionType.REVIEW
            elif current_stage == "negotiation_rounds":
                default_action_type = ActionType.NEGOTIATE
            
            # 创建默认规划
            plan = AgentPlan(
                agent_id=agent_id,
                goal=goal,
                steps=[
                    PlanStep(
                        step_id="default_step_1",
                        description=f"执行{agent.name}在当前阶段的任务",
                        action_type=default_action_type,
                        status="pending"
                    )
                ]
            )
            agent.state.plan = plan
        
        # 5. 执行规划中的下一步
        next_step = None
        for step in plan.steps:
            if step.status == "pending":
                next_step = step
                break
        
        if next_step:
            next_step.status = "in_progress"
            action = {
                "description": next_step.description,
                "action_type": next_step.action_type,
                "step_id": next_step.step_id
            }
            
            # 6. 行动
            result = await agent.act(action, shared_state)
            
            # 更新步骤状态
            if "error" not in result:
                next_step.status = "completed"
                next_step.result = str(result)
            else:
                next_step.status = "failed"
            
            # 更新Agent状态到共享状态
            shared_state.agents[agent_id] = agent.get_state()
            
            return {
                "agent_id": agent_id,
                "action": action,
                "result": result,
                "status": "completed"
            }
        else:
            # 所有步骤完成，标记规划完成
            plan.is_active = False
            agent.state.status = agent.state.status  # 保持当前状态
            shared_state.agents[agent_id] = agent.get_state()
            
            return {
                "agent_id": agent_id,
                "status": "plan_completed",
                "message": "所有规划步骤已完成"
            }
    
    async def run_agents_concurrent(
        self,
        agent_ids: List[str],
        shared_state: SharedState,
        max_concurrent: int = 3
    ) -> List[Dict]:
        """
        并发运行多个Agent
        """
        results = []
        
        # 使用信号量控制并发数
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def run_with_semaphore(agent_id: str):
            async with semaphore:
                return await self.run_agent_cycle(agent_id, shared_state)
        
        # 并发执行
        tasks = [run_with_semaphore(agent_id) for agent_id in agent_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "agent_id": agent_ids[i],
                    "error": str(result),
                    "status": "failed"
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    def get_agent_by_role(self, role: AgentRole) -> Optional[BaseAgent]:
        """根据角色获取Agent"""
        for agent_id, agent_role in self.agent_roles.items():
            if agent_role == role:
                return self.agents.get(agent_id)
        return None
    
    def get_department_agents(self) -> List[BaseAgent]:
        """获取所有部门Agent"""
        return [
            agent for agent_id, agent in self.agents.items()
            if self.agent_roles.get(agent_id) in [
                AgentRole.FINANCE, AgentRole.LEGAL, AgentRole.PLANNING,
                AgentRole.INDUSTRY, AgentRole.ENVIRONMENT, AgentRole.SECURITY
            ]
        ]
    
    def get_office_agent(self) -> Optional[OfficeAgent]:
        """获取办公厅Agent"""
        return self.get_agent_by_role(AgentRole.OFFICE)
    
    def get_decider_agent(self) -> Optional[DeciderAgent]:
        """获取决策者Agent"""
        return self.get_agent_by_role(AgentRole.DECIDER)

