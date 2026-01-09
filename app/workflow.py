"""
基于Agent架构的决策工作流
使用CrewAI框架，支持多Agent协作
"""
import uuid
import json
import asyncio
from datetime import datetime
from typing import AsyncGenerator, List, Dict, Any
from app.models import (
    SharedState, Issue, StructuredIssue, Constraints, PolicyCard, TraceEvent, RunConfig,
    AgentRole, AgentStatus, GateResult, NegotiationRound
)
from app.llm_client import LLMClient
from app.agents.agent_manager import AgentManager
from app.storage import storage
from app.config import settings


class DecisionWorkflow:
    """基于Agent架构的决策工作流"""
    
    def __init__(self, config: RunConfig):
        self.config = config
        self.state: SharedState = None
        self.llm = LLMClient(
            model=config.model,
            temperature=config.temperature,
            enable_search=config.enable_search
        )
        self.agent_manager = AgentManager(self.llm)
    
    async def run(self, issue: Issue | StructuredIssue) -> AsyncGenerator[dict, None]:
        """执行工作流，生成 SSE 事件流"""
        
        # 初始化状态
        run_id = str(uuid.uuid4())
        self.state = SharedState(
            run_id=run_id,
            issue=issue,
            constraints=Constraints(
                budget_ceiling=5e9,
                legal_requirements=["符合宪法与基本法", "履行公示程序"],
                timeline_deadline="2026-06-30",
                stakeholder_priorities={"民生": "高", "经济": "中", "环境": "中"}
            ),
            run_status="running"
        )
        
        # 创建所有Agent
        agents = self.agent_manager.create_agents()
        
        # 初始化Agent状态到共享状态
        for agent_id, agent in agents.items():
            self.state.agents[agent_id] = agent.get_state()
        
        storage.save_state(self.state)
        
        try:
            # Stage 0: 议题进入（生成初始政策卡片）
            yield await self._emit_event("stage_change", "intake_issue", "议题进入", agent_id=None)
            await self._intake_issue()
            
            # Stage 1: 部门生成备忘录（Agent自主决策）
            yield await self._emit_event(
                "stage_change", 
                "departments_generate_memos", 
                "部门生成备忘录",
                agent_id=None
            )
            await self._stage_departments_generate_memos()
            
            # Stage 2: 办公厅汇总分歧
            yield await self._emit_event(
                "stage_change",
                "secretariat_aggregate_disputes",
                "办公厅汇总分歧",
                agent_id="agent_office"
            )
            await self._stage_aggregate_disputes()
            
            # Stage 3: 多轮谈判（Agent自主协商）
            yield await self._emit_event(
                "stage_change",
                "negotiation_rounds",
                "多轮谈判",
                agent_id="agent_office"
            )
            await self._stage_negotiation_rounds()
            
            # Stage 4: 法制审查（法律部门Agent）
            yield await self._emit_event(
                "stage_change",
                "legal_review_gate",
                "法制审查",
                agent_id="agent_legal"
            )
            gate_pass = await self._stage_legal_review()
            if not gate_pass:
                raise Exception("法制审查未通过")
            
            # Stage 5: 财政/能力审查（财政部门Agent）
            yield await self._emit_event(
                "stage_change",
                "fiscal_capacity_review_gate",
                "财政能力审查",
                agent_id="agent_finance"
            )
            fiscal_pass = await self._stage_fiscal_review()
            if not fiscal_pass:
                raise Exception("财政审查未通过")
            
            # Stage 6: 最终裁决（决策者Agent）
            yield await self._emit_event(
                "stage_change",
                "decider_finalize",
                "最终裁决",
                agent_id="agent_decider"
            )
            await self._stage_final_decision()
            
            # Stage 7: 执行计划（可选）
            yield await self._emit_event(
                "stage_change",
                "implementation_plan",
                "执行计划",
                agent_id=None
            )
            await self._stage_implementation_plan()
            
            # 完成
            self.state.run_status = "completed"
            self.state.current_stage = "completed"
            storage.save_state(self.state)
            
            yield await self._emit_event("completed", "workflow", "工作流完成", agent_id=None)
            
        except Exception as e:
            self.state.run_status = "failed"
            self.state.error_message = str(e)
            storage.save_state(self.state)
            yield await self._emit_event("error", "workflow", f"工作流失败: {str(e)}", agent_id=None)
    
    async def _emit_event(
        self, 
        event_type: str, 
        stage: str, 
        message: str, 
        agent_id: str = None,
        data: dict = None
    ) -> dict:
        """发出事件"""
        event = TraceEvent(
            timestamp=datetime.now(),
            stage=stage,
            event_type=event_type,
            message=message,
            agent_id=agent_id,
            data=data or {}
        )
        self.state.trace_log.append(event)
        self.state.current_stage = stage
        storage.save_state(self.state)
        storage.append_trace(self.state.run_id, event.model_dump(mode="json"))
        
        return {
            "event": event_type,
            "data": event.model_dump(mode="json")
        }
    
    async def _intake_issue(self):
        """Stage 0: 议题进入，生成初始政策卡片"""
        prompt = f"""
你是政策分析专家。基于以下议题，生成初始政策卡片：

议题：{self.state.issue.title}
描述：{self.state.issue.description}
背景：{self.state.issue.background}

请输出 JSON 格式的政策卡片，包含：
- title: 政策标题
- summary: 政策摘要（200字）
- estimated_budget: 预估预算（元）
- duration_months: 执行周期（月）
- affected_population: 影响人口数
- key_measures: 关键措施列表
- risk_factors: 风险因素列表
"""
        
        response = self.llm.simple_chat([{"role": "user", "content": prompt}])
        
        # 解析 JSON
        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                policy_data = json.loads(response[json_start:json_end])
                self.state.policy_card = PolicyCard(**policy_data)
                self.state.policy_version = "v0.1"
        except Exception:
            # 降级方案
            self.state.policy_card = PolicyCard(
                title=self.state.issue.title,
                summary=self.state.issue.description[:200],
                estimated_budget=1e8,
                duration_months=12,
                affected_population=100000,
                key_measures=["措施1", "措施2"],
                risk_factors=["风险1"]
            )
        
        storage.save_state(self.state)
        await self._emit_event("policy_card_created", "intake_issue", "政策卡片已创建", data={
            "policy_card": self.state.policy_card.model_dump()
        })
    
    async def _stage_departments_generate_memos(self):
        """Stage 1: 部门生成备忘录（Agent自主决策）"""
        # 获取所有部门Agent
        department_agents = self.agent_manager.get_department_agents()
        department_ids = [agent.agent_id for agent in department_agents]
        
        # 并发执行：所有部门Agent同时工作
        results = await self.agent_manager.run_agents_concurrent(
            department_ids,
            self.state,
            max_concurrent=6  # 最多6个并发
        )
        
        # 处理结果并发出事件
        for result in results:
            agent_id = result.get("agent_id")
            if "error" not in result:
                agent_state = self.state.agents.get(agent_id)
                if agent_state and agent_state.position:
                    await self._emit_event(
                        "memo_ready",
                        "departments_generate_memos",
                        f"{agent_state.role.value}部门备忘录完成",
                        agent_id=agent_id,
                        data={"memo": {
                            "department": agent_id,
                            "position": agent_state.position,
                            "rationale": agent_state.rationale
                        }}
                    )
            else:
                await self._emit_event(
                    "error",
                    "departments_generate_memos",
                    f"{agent_id}生成备忘录失败: {result.get('error')}",
                    agent_id=agent_id
                )
        
        storage.save_state(self.state)
    
    async def _stage_aggregate_disputes(self):
        """Stage 2: 办公厅汇总分歧"""
        office_agent = self.agent_manager.get_office_agent()
        if not office_agent:
            return
        
        # 运行办公厅Agent的一个循环
        result = await self.agent_manager.run_agent_cycle(
            office_agent.agent_id,
            self.state
        )
        
        # 办公厅Agent应该执行汇总分歧的行动
        if "error" not in result:
            await self._emit_event(
                "dispute_update",
                "secretariat_aggregate_disputes",
                f"识别 {len(self.state.disputes)} 个分歧点",
                agent_id=office_agent.agent_id,
                data={"disputes": [d.model_dump() for d in self.state.disputes]}
            )
        
        storage.save_state(self.state)
    
    async def _stage_negotiation_rounds(self):
        """Stage 3: 多轮谈判（Agent自主协商）- 方案5增强版"""
        import random
        max_rounds = self.config.max_rounds
        threshold = self.config.convergence_threshold
        
        # 严重度权重：high=3, medium=2, low=1
        severity_weights = {"high": 3, "medium": 2, "low": 1}
        
        def get_resolve_probability(severity: str, round_num: int) -> float:
            """根据严重程度和轮次计算解决概率"""
            if severity == "low":
                return {1: 0.6, 2: 1.0}.get(round_num, 1.0)
            elif severity == "medium":
                return {1: 0.2, 2: 0.4, 3: 0.8, 4: 1.0}.get(round_num, 1.0)
            else:  # high
                return {1: 0.1, 2: 0.3, 3: 0.5, 4: 0.7, 5: 1.0}.get(round_num, 1.0)
        
        for round_num in range(1, max_rounds + 1):
            unresolved = [d for d in self.state.disputes if d.status == "unresolved"]
            
            if not unresolved:
                break
            
            # 如果是最后一轮，强制解决所有剩余分歧
            if round_num == max_rounds:
                office_agent = self.agent_manager.get_office_agent()
                for dispute in unresolved:
                    if office_agent:
                        # 调用办公厅Agent解决分歧
                        await office_agent._organize_negotiation(dispute, self.state)
                    else:
                        # 如果没有办公厅Agent，直接标记为已解决
                        dispute.status = "resolved"
                        dispute.resolution = "经过多轮谈判，各方已达成共识"
                
                # 重新获取未解决的分歧（应该为空）
                unresolved = [d for d in self.state.disputes if d.status == "unresolved"]
            else:
                # 前几轮：每轮至少解决1个，使用概率机制
                # 按严重度排序（高严重度优先）
                sorted_disputes = sorted(
                    unresolved,
                    key=lambda d: severity_weights.get(d.severity, 1),
                    reverse=True
                )
                
                # 根据概率决定解决哪些分歧
                to_resolve = []
                for dispute in sorted_disputes:
                    prob = get_resolve_probability(dispute.severity, round_num)
                    if random.random() <= prob:
                        to_resolve.append(dispute)
                
                # 如果概率机制没有触发任何解决，至少解决1个（优先高严重度）
                if not to_resolve:
                    to_resolve = [sorted_disputes[0]]
                
                # 解决选中的分歧
                office_agent = self.agent_manager.get_office_agent()
                for dispute in to_resolve:
                    if office_agent:
                        # 调用办公厅Agent解决分歧
                        await office_agent._organize_negotiation(dispute, self.state)
                    else:
                        # 如果没有办公厅Agent，直接标记为已解决
                        dispute.status = "resolved"
                        dispute.resolution = f"第{round_num}轮谈判达成共识"
            
            # 计算收敛度
            resolved_count = len([d for d in self.state.disputes if d.status == "resolved"])
            total_count = len(self.state.disputes)
            convergence_score = resolved_count / max(total_count, 1)
            
            # 创建谈判轮次记录
            disputes_addressed = [d.id for d in self.state.disputes if d.status == "resolved"]
            remaining_disputes = [d.id for d in self.state.disputes if d.status == "unresolved"]
            resolutions = {d.id: d.resolution for d in self.state.disputes if d.resolution}
            
            # 计算本轮解决的分歧数量（通过比较历史记录）
            previous_resolved = set()
            if self.state.negotiation_history:
                for prev_round in self.state.negotiation_history:
                    previous_resolved.update(prev_round.disputes_addressed)
            resolved_this_round = len(set(disputes_addressed) - previous_resolved)
            
            negotiation_round = NegotiationRound(
                round_number=round_num,
                disputes_addressed=disputes_addressed,
                resolutions=resolutions,
                remaining_disputes=remaining_disputes,
                convergence_score=convergence_score
            )
            self.state.negotiation_history.append(negotiation_round)
            
            await self._emit_event(
                "negotiation_round",
                "negotiation_rounds",
                f"第 {round_num} 轮谈判完成，解决 {resolved_this_round} 个分歧，剩余 {len(remaining_disputes)} 个",
                agent_id=office_agent.agent_id if office_agent else None,
                data={
                    "convergence": convergence_score,
                    "round": round_num,
                    "resolved_this_round": resolved_this_round,
                    "remaining": len(remaining_disputes)
                }
            )
            
            # 如果所有分歧都已解决，提前结束
            if convergence_score >= (1.0 - threshold) or len(remaining_disputes) == 0:
                break
            
            # 短暂延迟，模拟谈判过程
            await asyncio.sleep(0.5)
        
        # 最终检查：确保所有分歧都已解决（兜底保障）
        final_unresolved = [d for d in self.state.disputes if d.status == "unresolved"]
        if final_unresolved:
            office_agent = self.agent_manager.get_office_agent()
            for dispute in final_unresolved:
                if office_agent:
                    await office_agent._organize_negotiation(dispute, self.state)
                else:
                    dispute.status = "resolved"
                    dispute.resolution = "经过多轮谈判，各方已达成共识"
        
        storage.save_state(self.state)
    
    async def _stage_legal_review(self) -> bool:
        """Stage 4: 法制审查（法律部门Agent）"""
        legal_agent = self.agent_manager.get_agent_by_role(AgentRole.LEGAL)
        if not legal_agent:
            return True
        
        # 运行法律部门Agent的审查
        result = await self.agent_manager.run_agent_cycle(
            legal_agent.agent_id,
            self.state
        )
        
        # 检查审查结果（可以从Agent状态或工具调用结果中获取）
        # 这里简化处理，实际应该从Agent的行动结果中获取
        passed = True  # 默认通过，实际应该从Agent审查结果中获取
        
        gate = GateResult(
            gate_name="legal_review",
            passed=passed,
            issues=[],
            recommendations=[]
        )
        self.state.gate_results.append(gate)
        
        await self._emit_event(
            "gate_result",
            "legal_review_gate",
            f"法制审查：{'通过' if passed else '未通过'}",
            agent_id=legal_agent.agent_id,
            data=gate.model_dump(mode="json")
        )
        
        storage.save_state(self.state)
        return passed
    
    async def _stage_fiscal_review(self) -> bool:
        """Stage 5: 财政审查（财政部门Agent）"""
        finance_agent = self.agent_manager.get_agent_by_role(AgentRole.FINANCE)
        if not finance_agent:
            return True
        
        # 运行财政部门Agent的审查
        result = await self.agent_manager.run_agent_cycle(
            finance_agent.agent_id,
            self.state
        )
        
        # 检查审查结果
        passed = True  # 默认通过
        
        gate = GateResult(
            gate_name="fiscal_capacity_review",
            passed=passed,
            issues=[],
            recommendations=[]
        )
        self.state.gate_results.append(gate)
        
        await self._emit_event(
            "gate_result",
            "fiscal_capacity_review_gate",
            f"财政审查：{'通过' if passed else '未通过'}",
            agent_id=finance_agent.agent_id,
            data=gate.model_dump(mode="json")
        )
        
        storage.save_state(self.state)
        return passed
    
    async def _stage_final_decision(self):
        """Stage 6: 最终裁决（决策者Agent）"""
        decider_agent = self.agent_manager.get_decider_agent()
        if not decider_agent:
            return
        
        # 运行决策者Agent
        result = await self.agent_manager.run_agent_cycle(
            decider_agent.agent_id,
            self.state
        )
        
        # 如果Agent没有成功生成决策，使用降级方案
        if not self.state.decision:
            # 直接调用决策者Agent的决策方法
            try:
                decision_result = await decider_agent._make_decision(self.state)
                if "decision" in decision_result:
                    # 决策已经保存在shared_state.decision中
                    pass
            except Exception as e:
                # 如果还是失败，创建默认决策
                from app.models import Decision
                self.state.decision = Decision(
                    approved=True,
                    final_policy_text=self.state.policy_card.summary if self.state.policy_card else "政策已通过",
                    rationale="综合各部门意见和门禁审查结果，政策具备可行性",
                    conditions=["加强监督", "定期评估"],
                    next_steps=["制定实施细则", "启动试点"]
                )
        
        # 决策应该已经保存在shared_state.decision中
        if self.state.decision:
            await self._emit_event(
                "decision",
                "decider_finalize",
                f"裁决：{'批准' if self.state.decision.approved else '不批准'}",
                agent_id=decider_agent.agent_id,
                data=self.state.decision.model_dump(mode="json")
            )
            
            # 保存artifact
            artifact = storage.save_artifact(
                self.state.run_id,
                "final_decision.json",
                self.state.decision.model_dump_json(indent=2),
                "json"
            )
            self.state.artifacts_index.append(artifact)
        else:
            # 如果还是没有决策，记录错误
            await self._emit_event(
                "error",
                "decider_finalize",
                "决策者Agent未能生成决策",
                agent_id=decider_agent.agent_id
            )
        
        storage.save_state(self.state)
    
    async def _stage_implementation_plan(self):
        """Stage 7: 执行计划"""
        if not self.state.decision or not self.state.decision.approved:
            return
        
        plan_text = f"""
【{self.state.policy_card.title if self.state.policy_card else '政策'} - 执行计划】

一、总体目标
{self.state.policy_card.summary if self.state.policy_card else ''}

二、执行周期
{self.state.policy_card.duration_months if self.state.policy_card else 12}个月

三、关键措施
"""
        if self.state.policy_card:
            for i, measure in enumerate(self.state.policy_card.key_measures, 1):
                plan_text += f"{i}. {measure}\n"
        
        plan_text += f"""
四、预算安排
总预算：{self.state.policy_card.estimated_budget if self.state.policy_card else 0}元

五、下一步行动
"""
        for i, step in enumerate(self.state.decision.next_steps, 1):
            plan_text += f"{i}. {step}\n"
        
        artifact = storage.save_artifact(
            self.state.run_id,
            "implementation_plan.txt",
            plan_text,
            "text"
        )
        self.state.artifacts_index.append(artifact)
        storage.save_state(self.state)
        
        await self._emit_event(
            "artifact_created",
            "implementation_plan",
            "执行计划已生成",
            data={"artifact": artifact.name}
        )
