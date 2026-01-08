import asyncio
import json
import sys
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sse_starlette.sse import EventSourceResponse
# Ensure project root is importable when running as a script (python app/main.py)
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.models import Issue, RunConfig
from app.workflow import DecisionWorkflow
from app.storage import storage
from app.config import settings


# 创建 FastAPI 应用
app = FastAPI(title="政府部门多智能体决策仿真系统")

# 静态文件与模板 - 使用绝对路径
static_dir = BASE_DIR / "static"
templates_dir = BASE_DIR / "templates"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(templates_dir))

# 活动的工作流实例
active_workflows = {}


# ===== 示例议题加载 =====
def load_sample_issues():
    issues_dir = Path("data/issues")
    issues = []
    for issue_file in issues_dir.glob("*.json"):
        with open(issue_file, "r", encoding="utf-8") as f:
            issue_data = json.load(f)
            issues.append(Issue(**issue_data))
    return issues


SAMPLE_ISSUES = load_sample_issues()


# ===== 页面路由 =====

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """首页：选择议题"""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "issues": SAMPLE_ISSUES
    })


@app.get("/runs", response_class=HTMLResponse)
async def runs_list(request: Request):
    """历史 run 列表"""
    runs = storage.list_runs()
    return templates.TemplateResponse("runs.html", {
        "request": request,
        "runs": runs
    })


@app.get("/runs/{run_id}", response_class=HTMLResponse)
async def run_detail(request: Request, run_id: str):
    """实时工作台"""
    try:
        state = storage.load_state(run_id)
        return templates.TemplateResponse("run_detail.html", {
            "request": request,
            "run_id": run_id,
            "state": state
        })
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="运行记录未找到")


@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    """API 配置页面"""
    return templates.TemplateResponse("setup.html", {
        "request": request,
        "current_api_key": settings.dashscope_api_key
    })


# ===== API 路由 =====

@app.post("/api/runs")
async def create_run(config: RunConfig):
    """创建 run"""
    # 获取议题
    if config.issue_id:
        issue = next((i for i in SAMPLE_ISSUES if i.id == config.issue_id), None)
        if not issue:
            raise HTTPException(status_code=404, detail="议题未找到")
    elif config.custom_issue:
        issue = config.custom_issue
    else:
        raise HTTPException(status_code=400, detail="需要提供 issue_id 或 custom_issue")
    
    # 创建工作流
    workflow = DecisionWorkflow(config)
    
    # 后台运行
    run_id = None
    async def run_workflow():
        nonlocal run_id
        async for event in workflow.run(issue):
            if run_id is None:
                run_id = workflow.state.run_id
                active_workflows[run_id] = workflow
    
    asyncio.create_task(run_workflow())
    
    # 等待 run_id
    for _ in range(10):
        await asyncio.sleep(0.1)
        if run_id:
            break
    
    if not run_id:
        raise HTTPException(status_code=500, detail="创建运行失败")
    
    return {"run_id": run_id}


@app.get("/api/runs")
async def get_runs():
    """获取 runs 列表"""
    return storage.list_runs()


@app.delete("/api/runs/{run_id}")
async def delete_run(run_id: str):
    """删除 run"""
    try:
        storage.delete_run(run_id)
        return {"success": True, "message": "删除成功"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="运行记录未找到")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败：{str(e)}")


@app.get("/api/runs/{run_id}/state")
async def get_run_state(run_id: str):
    """获取 run 状态"""
    try:
        state = storage.load_state(run_id)
        return JSONResponse(content=state.model_dump(mode="json"))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="运行记录未找到")


@app.get("/api/runs/{run_id}/events")
async def run_events(run_id: str):
    """SSE 事件流"""
    
    async def event_generator():
        # 先发送历史事件
        try:
            state = storage.load_state(run_id)
            for event in state.trace_log:
                yield {
                    "event": event.event_type,
                    "data": json.dumps(event.model_dump(mode="json"), ensure_ascii=False)
                }
                await asyncio.sleep(0.05)
        except FileNotFoundError:
            pass
        
        # 如果 workflow 正在运行，监听新事件
        if run_id in active_workflows:
            workflow = active_workflows[run_id]
            last_count = len(workflow.state.trace_log)
            
            while workflow.state.run_status == "running":
                await asyncio.sleep(0.5)
                
                # 检查新事件
                current_count = len(workflow.state.trace_log)
                if current_count > last_count:
                    for event in workflow.state.trace_log[last_count:]:
                        yield {
                            "event": event.event_type,
                            "data": json.dumps(event.model_dump(mode="json"), ensure_ascii=False)
                        }
                    last_count = current_count
            
            # 发送完成事件
            yield {
                "event": "completed" if workflow.state.run_status == "completed" else "error",
                "data": json.dumps({
                    "status": workflow.state.run_status,
                    "error": workflow.state.error_message
                }, ensure_ascii=False)
            }
            
            # 清理
            del active_workflows[run_id]
    
    return EventSourceResponse(event_generator())


@app.get("/api/runs/{run_id}/artifacts")
async def get_artifacts(run_id: str):
    """获取 artifacts 列表"""
    try:
        state = storage.load_state(run_id)
        return [artifact.model_dump(mode="json") for artifact in state.artifacts_index]
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="运行记录未找到")


@app.get("/api/runs/{run_id}/artifacts/{artifact_name}")
async def download_artifact(run_id: str, artifact_name: str):
    """下载 artifact"""
    try:
        content = storage.load_artifact(run_id, artifact_name)
        
        # 确定 MIME 类型
        if artifact_name.endswith(".json"):
            media_type = "application/json"
        elif artifact_name.endswith(".txt"):
            media_type = "text/plain"
        else:
            media_type = "application/octet-stream"
        
        return HTMLResponse(content=content, media_type=media_type)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="文件未找到")


@app.post("/api/config/save")
async def save_config(config_data: dict):
    """保存 API 配置到 .env 文件"""
    try:
        api_key = config_data.get("api_key", "").strip()
        base_url = config_data.get("base_url", "").strip()
        
        if not api_key:
            raise HTTPException(status_code=400, detail="API Key 不能为空")
        
        # 写入 .env 文件
        env_path = Path(".env")
        env_content = f"""# 通义千问 API 配置
DASHSCOPE_API_KEY={api_key}
"""
        if base_url:
            env_content += f"DASHSCOPE_BASE_URL={base_url}\n"
        
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(env_content)
        
        # 更新当前 settings（需要重启才能完全生效）
        settings.dashscope_api_key = api_key
        if base_url:
            settings.dashscope_base_url = base_url
        
        return {
            "success": True,
            "message": "配置已保存！重启服务后生效。",
            "file": str(env_path.absolute())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败：{str(e)}")


@app.post("/api/config/test")
async def test_config(config_data: dict):
    """测试 API 连接"""
    try:
        api_key = config_data.get("api_key", "").strip()
        
        if not api_key:
            return {"success": False, "error": "API Key 不能为空"}
        
        # 简单测试：尝试创建客户端
        from openai import OpenAI
        test_client = OpenAI(
            api_key=api_key,
            base_url=settings.dashscope_base_url
        )
        
        # 发送一个简单请求
        response = test_client.chat.completions.create(
            model="qwen-plus",
            messages=[{"role": "user", "content": "测试"}],
            max_tokens=10
        )
        
        return {
            "success": True,
            "model": response.model,
            "message": "连接成功"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# ===== 启动 =====

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
