from typing import Dict, Any, List
from pydantic import BaseModel


# ===== Tool Schemas for Function Calling =====
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "impact_estimate",
            "description": "估算政策对经济、就业、通胀等的影响",
            "parameters": {
                "type": "object",
                "properties": {
                    "policy_card": {
                        "type": "object",
                        "description": "政策卡片，包含标题、摘要、预算等信息"
                    },
                    "scenario": {
                        "type": "string",
                        "description": "情景假设（baseline/optimistic/pessimistic）",
                        "enum": ["baseline", "optimistic", "pessimistic"]
                    }
                },
                "required": ["policy_card", "scenario"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "public_opinion_sim",
            "description": "模拟公众舆情反应，评估支持率、波动性与关切点",
            "parameters": {
                "type": "object",
                "properties": {
                    "policy_card": {
                        "type": "object",
                        "description": "政策卡片"
                    },
                    "context": {
                        "type": "string",
                        "description": "背景信息"
                    }
                },
                "required": ["policy_card", "context"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "stakeholder_analysis",
            "description": "分析政策对利益相关者的影响",
            "parameters": {
                "type": "object",
                "properties": {
                    "policy_card": {
                        "type": "object",
                        "description": "政策卡片"
                    },
                    "stakeholder_type": {
                        "type": "string",
                        "description": "利益相关者类型（citizens/businesses/government）"
                    }
                },
                "required": ["policy_card", "stakeholder_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "risk_assessment",
            "description": "评估政策实施风险",
            "parameters": {
                "type": "object",
                "properties": {
                    "policy_card": {
                        "type": "object",
                        "description": "政策卡片"
                    },
                    "risk_category": {
                        "type": "string",
                        "description": "风险类别（financial/operational/legal/social）"
                    }
                },
                "required": ["policy_card", "risk_category"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "feasibility_check",
            "description": "检查政策实施的可行性",
            "parameters": {
                "type": "object",
                "properties": {
                    "policy_card": {
                        "type": "object",
                        "description": "政策卡片"
                    },
                    "aspect": {
                        "type": "string",
                        "description": "可行性方面（technical/financial/timeline/resource）"
                    }
                },
                "required": ["policy_card", "aspect"]
            }
        }
    }
]


# ===== Tool Implementations (Deterministic Stubs) =====

def impact_estimate(policy_card: Dict[str, Any], scenario: str) -> Dict[str, Any]:
    """影响估算（确定性 stub）"""
    budget = policy_card.get("estimated_budget", 0)
    affected = policy_card.get("affected_population", 0)
    
    # 确定性系数
    scenario_multipliers = {
        "baseline": 1.0,
        "optimistic": 1.5,
        "pessimistic": 0.6
    }
    multiplier = scenario_multipliers.get(scenario, 1.0)
    
    gdp_delta = (budget / 1e9) * 0.02 * multiplier  # 2% GDP影响率
    employment_delta = int((budget / 1e6) * 5 * multiplier)  # 每百万创造5个就业
    inflation_delta = (budget / 1e10) * 0.001 * multiplier  # 微小通胀效应
    
    distributional_notes = f"{scenario} 情景：预计直接受益人群 {affected}，间接影响人群 {affected * 3}。"
    
    return {
        "gdp_delta": round(gdp_delta, 4),
        "employment_delta": employment_delta,
        "inflation_delta": round(inflation_delta, 4),
        "distributional_notes": distributional_notes
    }


def public_opinion_sim(policy_card: Dict[str, Any], context: str) -> Dict[str, Any]:
    """舆情模拟（确定性 stub）"""
    title = policy_card.get("title", "")
    risk_factors = policy_card.get("risk_factors", [])
    
    # 基础支持率（基于风险因素数量）
    base_support = 0.65 - len(risk_factors) * 0.05
    base_support = max(0.3, min(0.9, base_support))
    
    # 确定性波动率
    volatility = 0.1 + len(risk_factors) * 0.02
    
    # 关切点（确定性规则）
    concerns = []
    if "财政" in context or "预算" in context:
        concerns.append("财政负担")
    if "时间" in context or "紧急" in context:
        concerns.append("执行时效")
    if len(risk_factors) > 2:
        concerns.append("政策风险")
    if not concerns:
        concerns.append("信息透明度")
    
    return {
        "support_rate": round(base_support, 2),
        "volatility": round(volatility, 2),
        "key_concerns": concerns
    }


def stakeholder_analysis(policy_card: Dict[str, Any], stakeholder_type: str) -> Dict[str, Any]:
    """利益相关者分析"""
    title = policy_card.get("title", "")
    affected = policy_card.get("affected_population", 0)
    measures = policy_card.get("key_measures", [])
    
    analysis = {
        "citizens": {
            "impact_level": "medium",
            "benefits": ["提升公共服务质量", "改善生活环境"],
            "concerns": ["可能增加税收负担", "政策执行效果"],
            "engagement_level": "high"
        },
        "businesses": {
            "impact_level": "medium",
            "benefits": ["市场机会", "政策支持"],
            "concerns": ["合规成本", "竞争环境变化"],
            "engagement_level": "medium"
        },
        "government": {
            "impact_level": "high",
            "benefits": ["政策目标达成", "治理能力提升"],
            "concerns": ["财政压力", "执行难度"],
            "engagement_level": "high"
        }
    }
    
    result = analysis.get(stakeholder_type, analysis["citizens"])
    result["affected_population"] = affected
    result["policy_title"] = title
    
    return result


def risk_assessment(policy_card: Dict[str, Any], risk_category: str) -> Dict[str, Any]:
    """风险评估"""
    budget = policy_card.get("estimated_budget", 0)
    duration = policy_card.get("duration_months", 12)
    risk_factors = policy_card.get("risk_factors", [])
    
    risk_levels = {
        "financial": {
            "level": "medium" if budget > 1e9 else "low",
            "risks": ["预算超支", "资金来源不稳定"],
            "mitigation": ["建立预算监控机制", "多元化资金来源"]
        },
        "operational": {
            "level": "medium",
            "risks": ["执行能力不足", "时间延误"],
            "mitigation": ["加强能力建设", "建立时间节点监控"]
        },
        "legal": {
            "level": "low",
            "risks": ["法律依据不足", "程序合规性"],
            "mitigation": ["完善法律依据", "严格履行程序"]
        },
        "social": {
            "level": "medium" if len(risk_factors) > 2 else "low",
            "risks": ["公众接受度", "利益冲突"],
            "mitigation": ["加强沟通", "利益平衡机制"]
        }
    }
    
    result = risk_levels.get(risk_category, risk_levels["financial"])
    result["category"] = risk_category
    result["existing_risk_factors"] = risk_factors
    
    return result


def feasibility_check(policy_card: Dict[str, Any], aspect: str) -> Dict[str, Any]:
    """可行性检查"""
    budget = policy_card.get("estimated_budget", 0)
    duration = policy_card.get("duration_months", 12)
    measures = policy_card.get("key_measures", [])
    
    checks = {
        "technical": {
            "feasible": True,
            "score": 0.8,
            "issues": ["需要技术支持", "需要专业人才"],
            "recommendations": ["技术方案论证", "人才引进计划"]
        },
        "financial": {
            "feasible": budget <= 5e9,
            "score": 0.7 if budget <= 5e9 else 0.4,
            "issues": ["预算规模较大"] if budget > 5e9 else [],
            "recommendations": ["分阶段实施", "寻求外部资金"]
        },
        "timeline": {
            "feasible": duration <= 60,
            "score": 0.75 if duration <= 60 else 0.5,
            "issues": ["执行周期较长"] if duration > 60 else [],
            "recommendations": ["优化时间安排", "关键路径管理"]
        },
        "resource": {
            "feasible": len(measures) <= 10,
            "score": 0.7 if len(measures) <= 10 else 0.5,
            "issues": ["措施较多，资源需求大"] if len(measures) > 10 else [],
            "recommendations": ["资源整合", "优先级排序"]
        }
    }
    
    result = checks.get(aspect, checks["technical"])
    result["aspect"] = aspect
    
    return result


# ===== Tool Dispatcher =====

def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """执行工具调用"""
    if tool_name == "impact_estimate":
        return impact_estimate(
            arguments.get("policy_card", {}),
            arguments.get("scenario", "baseline")
        )
    elif tool_name == "public_opinion_sim":
        return public_opinion_sim(
            arguments.get("policy_card", {}),
            arguments.get("context", "")
        )
    elif tool_name == "stakeholder_analysis":
        return stakeholder_analysis(
            arguments.get("policy_card", {}),
            arguments.get("stakeholder_type", "citizens")
        )
    elif tool_name == "risk_assessment":
        return risk_assessment(
            arguments.get("policy_card", {}),
            arguments.get("risk_category", "financial")
        )
    elif tool_name == "feasibility_check":
        return feasibility_check(
            arguments.get("policy_card", {}),
            arguments.get("aspect", "technical")
        )
    else:
        return {"error": f"未知工具: {tool_name}"}


# ===== 工具函数（直接导出，不使用装饰器） =====

# 导出所有工具函数（用于Agent调用）
TOOLS = {
    "impact_estimate": impact_estimate,
    "public_opinion_sim": public_opinion_sim,
    "stakeholder_analysis": stakeholder_analysis,
    "risk_assessment": risk_assessment,
    "feasibility_check": feasibility_check
}

# 为了兼容性，保留 CREWAI_TOOLS（但实际不使用装饰器）
CREWAI_TOOLS = list(TOOLS.values())
