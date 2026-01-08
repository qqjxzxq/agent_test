import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API 密钥
    dashscope_api_key: str = os.getenv("DASHSCOPE_API_KEY", "")
    
    # LLM 配置
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    default_model: str = "qwen-plus"
    decider_model: str = "qwen-max"
    default_temperature: float = 0.7
    
    # 工作流配置
    max_negotiation_rounds: int = 5
    convergence_threshold: float = 0.15
    
    # 存储
    artifacts_dir: str = "./artifacts"
    
    class Config:
        env_file = ".env"


settings = Settings()
