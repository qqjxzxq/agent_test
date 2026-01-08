# 政府部门多智能体决策仿真系统

基于 **Python 3.11 + FastAPI + CrewAI + Jinja2 + HTMX + SSE** 的政府部门多智能体决策仿真系统，使用真正的Agent架构模拟多部门协作、谈判、门禁审查与最终裁决的完整流程。

## 功能特性

- ✅ **真正的多智能体架构**：使用CrewAI框架，每个部门都是独立的Agent
- ✅ **观察-思考-行动循环**：每个Agent具备自主决策能力，能观察环境、思考策略、执行行动
- ✅ **Agent间通信机制**：支持Agent之间的消息传递、协商和协作
- ✅ **局部规划与动态调整**：每个Agent能自主生成规划，并根据环境变化动态调整
- ✅ **8阶段决策流程**：议题进入 → 部门备忘录 → 汇总分歧 → 多轮谈判 → 法制审查 → 财政审查 → 最终裁决 → 执行计划
- ✅ **并发执行**：多个Agent可以并发工作，提高效率
- ✅ **实时 SSE 事件流**：前端通过 Server-Sent Events 实时接收工作流进度和Agent活动
- ✅ **LLM Function Calling**：集成通义千问（百炼），支持 5 个工具（影响估算、舆情模拟、利益相关者分析、风险评估、可行性检查）
- ✅ **HTML 控制台**：服务端渲染（Jinja2），使用 HTMX 实现局部刷新，展示Agent活动和通信
- ✅ **本地持久化**：所有 run 状态、Agent状态与产出文件存储在 `artifacts/` 目录
- ✅ **3 个示例议题**：公交电动化、中小企业数字化、老旧小区改造

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11 + FastAPI + Uvicorn |
| Agent框架 | CrewAI |
| 前端 | Jinja2 Templates + HTMX (SSE 扩展) |
| 实时 | sse-starlette (EventSourceResponse) |
| 数据模型 | Pydantic v2 |
| LLM | 通义千问（DashScope OpenAI 兼容模式）|
| 存储 | 本地文件系统（JSON/JSONL/TXT）|

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

**Python 版本要求**：Python 3.11+

### 2. 配置环境变量

创建 `.env` 文件或设置环境变量：

```bash
# Windows PowerShell
$env:DASHSCOPE_API_KEY="sk-your-api-key"

# Linux/macOS
export DASHSCOPE_API_KEY="sk-your-api-key"
```

> 获取 API Key：访问 [阿里云百炼平台](https://dashscope.console.aliyun.com/)

### 3. 启动服务

**方式 1：使用 Makefile**

```bash
make run
```

**方式 2：直接运行**

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**方式 3：使用 main.py**

```bash
python app/main.py
```

### 4. 访问系统

打开浏览器访问：**http://localhost:8000**

## 使用指南

### 创建仿真任务

1. 访问首页 `http://localhost:8000`
2. 选择一个示例议题（或自定义议题）
3. 配置参数：
   - 最大谈判轮次（默认 5）
   - 收敛阈值（默认 0.15）
   - LLM 模型（推荐 `qwen-plus`）
   - Temperature（默认 0.7）
   - 启用联网搜索（可选）
   - 启用舆情模拟（可选）
4. 点击「开始仿真」

### 实时监控

跳转到实时工作台页面，可以看到：

- **阶段 Stepper**：当前执行阶段高亮
- **实时时间线**：事件流滚动显示
- **部门备忘录**：各部门的立场、关切点、建议
- **分歧点列表**：识别的部门分歧与解决状态
- **门禁结果**：法制门禁与财政门禁的审查结果
- **最终决策**：批准/不批准、政策文本、决策理由
- **产出文件**：可下载最终决策、执行计划等 JSON/TXT 文件

### 查看历史

访问 `http://localhost:8000/runs` 查看所有历史仿真记录。

## 目录结构

```
.
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 应用入口
│   ├── models.py            # Pydantic 数据模型
│   ├── workflow.py          # 决策仿真工作流
│   ├── llm_client.py        # 通义千问 LLM 客户端
│   ├── tools.py             # Function Calling 工具
│   ├── storage.py           # 本地持久化
│   └── config.py            # 配置
├── templates/
│   ├── index.html           # 首页（选择议题）
│   ├── runs.html            # 历史 run 列表
│   └── run_detail.html      # 实时工作台
├── static/
│   ├── style.css            # 样式
│   └── app.js               # 前端逻辑
├── data/
│   └── issues/
│       ├── issue_1.json     # 示例议题 1
│       ├── issue_2.json     # 示例议题 2
│       └── issue_3.json     # 示例议题 3
├── artifacts/               # 运行结果（自动创建）
├── requirements.txt
├── Makefile
└── README.md
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 首页（选择议题）|
| GET | `/runs` | 历史 run 列表 |
| GET | `/runs/{id}` | 实时工作台 |
| POST | `/api/runs` | 创建 run |
| GET | `/api/runs` | 获取 runs 列表 |
| GET | `/api/runs/{id}/state` | 获取 run 状态快照 |
| GET | `/api/runs/{id}/events` | **SSE 事件流** |
| GET | `/api/runs/{id}/artifacts` | 获取产出文件列表 |
| GET | `/api/runs/{id}/artifacts/{name}` | 下载产出文件 |

## SSE 事件类型

| 事件类型 | 说明 |
|---------|------|
| `stage_change` | 阶段切换 |
| `policy_card_created` | 政策卡片创建 |
| `memo_ready` | 部门备忘录完成（包含Agent ID） |
| `dispute_update` | 分歧点更新 |
| `negotiation_round` | 谈判轮次完成 |
| `tool_call` | 工具调用 |
| `gate_result` | 门禁结果 |
| `decision` | 最终决策 |
| `artifact_created` | 产出文件创建 |
| `completed` | 工作流完成 |
| `error` | 错误 |

所有事件都包含 `agent_id` 字段（如果相关），用于标识执行该操作的Agent。

## Agent架构

系统实现了真正的多智能体架构，包含8个Agent：

### 部门Agent（6个）
- **财政部Agent**：负责财政审查和预算评估
- **法制办Agent**：负责法律审查和合规性检查
- **规划局Agent**：负责政策规划和协调
- **工信局Agent**：负责产业政策分析
- **环保局Agent**：负责环境影响评估
- **安全局Agent**：负责安全风险评估

### 协调Agent（1个）
- **办公厅Agent**：负责协调各部门，汇总分歧，组织谈判

### 决策Agent（1个）
- **决策者Agent**：负责综合评估并做出最终决策

### Agent能力
每个Agent都具备：
- **观察能力**：感知环境状态、其他Agent状态、消息队列
- **思考能力**：基于观察进行推理和策略规划
- **规划能力**：根据当前阶段和目标，自主生成执行计划
- **行动能力**：执行规划中的步骤（生成备忘录、发送消息、使用工具等）
- **通信能力**：与其他Agent进行消息传递和协商
- **记忆能力**：保存观察、思考、行动和通信历史

## Function Calling 工具

系统实现了 5 个确定性工具（可复现结果）：

1. **`impact_estimate`**：估算经济影响（GDP、就业、通胀）
2. **`public_opinion_sim`**：模拟公众舆情（支持率、波动性、关切点）
3. **`stakeholder_analysis`**：分析政策对利益相关者的影响
4. **`risk_assessment`**：评估政策实施风险（财务、运营、法律、社会）
5. **`feasibility_check`**：检查政策实施的可行性（技术、财务、时间、资源）

> 工具逻辑为确定性 stub，便于调试与演示。生产环境可替换为真实数据库/API 调用。

## 配置说明

在 `app/config.py` 中可修改默认配置：

```python
class Settings(BaseSettings):
    dashscope_api_key: str          # 通义千问 API Key
    dashscope_base_url: str         # 默认：OpenAI 兼容端点
    default_model: str = "qwen-plus"
    decider_model: str = "qwen-max" # 裁决阶段使用更强模型
    default_temperature: float = 0.7
    max_negotiation_rounds: int = 5
    convergence_threshold: float = 0.15
    artifacts_dir: str = "./artifacts"
```

## 示例议题

系统内置 3 个示例议题：

1. **城市公共交通电动化转型政策**  
   紧迫性：高 | 涉及部门：交通、环保、财政、能源、规划

2. **中小企业数字化转型扶持计划**  
   紧迫性：中 | 涉及部门：工信、财政、科技、市场监管、人社

3. **老旧小区综合改造与适老化升级**  
   紧迫性：中 | 涉及部门：住建、民政、财政、规划、社区治理

## 常见问题

**Q：如何添加自定义议题？**  
A：在 `data/issues/` 目录下创建 JSON 文件，格式参考现有示例。重启服务后自动加载。

**Q：SSE 连接断开？**  
A：检查浏览器控制台。某些代理/防火墙可能阻止 SSE。本地测试建议直接访问 localhost。

**Q：API Key 无效？**  
A：确保在阿里云百炼平台开通服务并复制正确的 API Key。检查环境变量是否正确设置。

**Q：如何清理历史数据？**  
A：运行 `make clean` 或手动删除 `artifacts/` 目录。

## 开发说明

### Agent架构

系统使用CrewAI框架实现多智能体架构：

- **基础Agent类**：`app/agents/base_agent.py` - 实现观察-思考-行动循环
- **部门Agent**：`app/agents/department_agent.py` - 部门Agent实现
- **办公厅Agent**：`app/agents/office_agent.py` - 协调者Agent实现
- **决策者Agent**：`app/agents/decider_agent.py` - 决策者Agent实现
- **Agent管理器**：`app/agents/agent_manager.py` - Agent创建、协调和并发执行

### 添加新Agent

1. 在 `app/agents/` 目录下创建新的Agent类，继承 `BaseAgent`
2. 实现抽象方法：`_get_system_prompt()`, `_build_thinking_prompt()`, `_generate_memo()`
3. 在 `app/agents/agent_manager.py` 的 `create_agents()` 方法中注册

### 添加新工具

1. 在 `app/tools.py` 中添加工具函数与 schema
2. 在 `TOOL_SCHEMAS` 列表中注册
3. 在 `execute_tool` 函数中添加分发逻辑
4. 使用 `@tool` 装饰器创建CrewAI工具版本

### 修改工作流

编辑 `app/workflow.py` 的 `DecisionWorkflow` 类：
- 保留8阶段作为参考流程
- Agent在阶段内可以自主决策
- 使用 `agent_manager.run_agents_concurrent()` 实现并发执行

### 自定义前端

- 模板文件：`templates/*.html` - 包含Agent活动展示面板
- 样式文件：`static/style.css`
- 脚本文件：`static/app.js`

前端会实时展示：
- Agent状态（观察、思考、行动、规划等）
- Agent间的消息通信
- Agent的规划步骤
- Agent的行动历史

支持 HTMX 扩展与原生 JavaScript。

## 注意事项

⚠️ **本系统为仿真演示系统**，生成内容为模拟产物，不代表真实政府决策。  
⚠️ **禁止**生成包含真实政府公文抬头、文号的内容。  
⚠️ **生产部署**前需加强安全防护（认证、授权、输入校验、日志审计）。

## 许可证

MIT License

## 联系与支持

如有问题或建议，欢迎提交 Issue。
