# app/negotiation/engine.py
from typing import List, Dict, Any
from .models import NegotiationRound
from statistics import median


class NegotiationEngine:
    def __init__(self, agents):
        """
        agents: List[BaseAgent]
        """
        self.agents = agents

    # ========= Step 1: 每部门提出政策值 =========
    def collect_proposals(self, round_state: NegotiationRound, issue):
        proposals = {}

        for agent in self.agents:
            agent_proposals = {}

            for dim in issue.dimensions:
                agent_proposals[dim.id] = self.propose_policy_value(agent, dim)

            proposals[agent.role.value] = agent_proposals

        round_state.proposals = proposals

    def propose_policy_value(self, agent, dimension):
        """逻辑 + 包装一下"""
        w = agent.weights

        if dimension.type == "continuous":
            low, high = dimension.range
            mid = (low + high) / 2

            if "financial_cost" in w and w["financial_cost"] > 0.4:
                return low + 0.2 * (high - low)

            if "environmental_benefit" in w and w["environmental_benefit"] > 0.4:
                return high - 0.1 * (high - low)

            return mid

        elif dimension.type == "enum":
            options = dimension.options

            if "security_risk" in w and w["security_risk"] > 0.4:
                return options[0]

            if "industry_growth" in w and w["industry_growth"] > 0.4:
                return options[-1]

            return dimension.default

    # ========= Step 2：计算冲突 =========
    def compute_conflict(self, round_state: NegotiationRound, issue):
        max_gap = -1
        conflict_dim = None

        for dim in issue.dimensions:
            values = [
                round_state.proposals[a.role.value][dim.id]
                for a in self.agents
            ]

            if dim.type == "continuous":
                gap = max(values) - min(values)

            elif dim.type == "enum":
                gap = len(set(values)) - 1

            if gap > max_gap:
                max_gap = gap
                conflict_dim = dim.id

        round_state.conflict_dimension = conflict_dim
        round_state.conflict_level = max_gap

    # ========= Step 3：谈判 + 让步 =========
    def negotiate(self, round_state: NegotiationRound, issue):
        if round_state.conflict_level == 0:
            return True  # 无冲突，直接成功

        dim_id = round_state.conflict_dimension

        # 取所有值
        vals = {
            a.role.value: round_state.proposals[a.role.value][dim_id]
            for a in self.agents
        }

        # 简单让步策略：向平均靠 20%
        target = sum(vals.values()) / len(vals)

        new_vals = {}
        for role, v in vals.items():
            new_vals[role] = v * 0.8 + target * 0.2

        # 更新 proposals
        for agent in self.agents:
            round_state.proposals[agent.role.value][dim_id] = new_vals[agent.role.value]

        round_state.history.append({
            "action": "concession",
            "dimension": dim_id,
            "before": vals,
            "after": new_vals
        })

        return False

    # ========= Step 4：形成折中方案 =========
    def compute_compromise(self, round_state: NegotiationRound):
        compromise = {}

        for dim_id in next(iter(round_state.proposals.values())).keys():
            vals = [
                round_state.proposals[a.role.value][dim_id]
                for a in self.agents
            ]

            # 简化：中位数 当作折中
            compromise[dim_id] = median(vals)

        return compromise

    # ========= Step 5：总流程控制 =========
    def run(self, issue):
        round_state = NegotiationRound(
            round_id=1,
            issue_id=issue.id
        )

        MAX_ROUNDS = 3

        for r in range(1, MAX_ROUNDS + 1):
            round_state.round_id = r

            # 1️⃣ 收集提案
            self.collect_proposals(round_state, issue)

            # 2️⃣ 计算冲突
            self.compute_conflict(round_state, issue)

            if round_state.conflict_level == 0:
                compromise = self.compute_compromise(round_state)
                round_state.status = "resolved"
                return compromise, round_state

            # 3️⃣ 谈判
            finished = self.negotiate(round_state, issue)

            if finished:
                compromise = self.compute_compromise(round_state)
                round_state.status = "resolved"
                return compromise, round_state

        # ========= Step 5：强制政府协调 =========
        compromise = self.compute_compromise(round_state)
        round_state.status = "forced_resolution"
        return compromise, round_state
