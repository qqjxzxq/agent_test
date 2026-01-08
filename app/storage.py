import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from app.models import SharedState, Artifact
from app.config import settings


class Storage:
    def __init__(self):
        self.base_dir = Path(settings.artifacts_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def get_run_dir(self, run_id: str) -> Path:
        """获取 run 目录"""
        run_dir = self.base_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir
    
    def save_state(self, state: SharedState):
        """保存状态快照"""
        run_dir = self.get_run_dir(state.run_id)
        state_file = run_dir / "state.json"
        
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state.model_dump(mode="json"), f, ensure_ascii=False, indent=2)
    
    def load_state(self, run_id: str) -> SharedState:
        """加载状态"""
        run_dir = self.get_run_dir(run_id)
        state_file = run_dir / "state.json"
        
        if not state_file.exists():
            raise FileNotFoundError(f"运行 {run_id} 的状态文件未找到")
        
        with open(state_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return SharedState(**data)
    
    def append_trace(self, run_id: str, event: Dict[str, Any]):
        """追加 trace 事件"""
        run_dir = self.get_run_dir(run_id)
        trace_file = run_dir / "trace.jsonl"
        
        with open(trace_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    
    def save_artifact(self, run_id: str, name: str, content: str, artifact_type: str = "text") -> Artifact:
        """保存 artifact"""
        run_dir = self.get_run_dir(run_id)
        artifact_path = run_dir / name
        
        with open(artifact_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        size = artifact_path.stat().st_size
        
        return Artifact(
            name=name,
            type=artifact_type,
            path=str(artifact_path),
            size_bytes=size,
            created_at=datetime.now()
        )
    
    def load_artifact(self, run_id: str, name: str) -> str:
        """加载 artifact"""
        run_dir = self.get_run_dir(run_id)
        artifact_path = run_dir / name
        
        if not artifact_path.exists():
            raise FileNotFoundError(f"产出文件 {name} 未找到")
        
        with open(artifact_path, "r", encoding="utf-8") as f:
            return f.read()
    
    def list_runs(self) -> list:
        """列出所有 runs"""
        runs = []
        for run_dir in self.base_dir.iterdir():
            if run_dir.is_dir():
                state_file = run_dir / "state.json"
                if state_file.exists():
                    try:
                        with open(state_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        runs.append({
                            "run_id": data["run_id"],
                            "issue_title": data["issue"]["title"],
                            "status": data["run_status"],
                            "current_stage": data["current_stage"],
                            "created_at": data["created_at"]
                        })
                    except Exception:
                        pass
        
        runs.sort(key=lambda x: x["created_at"], reverse=True)
        return runs
    
    def delete_run(self, run_id: str):
        """删除 run 及其所有文件"""
        import shutil
        run_dir = self.base_dir / run_id
        
        if not run_dir.exists():
            raise FileNotFoundError(f"运行 {run_id} 未找到")
        
        shutil.rmtree(run_dir)


# 全局实例
storage = Storage()
