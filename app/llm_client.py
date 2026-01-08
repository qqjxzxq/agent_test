import json
from typing import Dict, Any, List, Optional
from openai import OpenAI
from app.config import settings
from app.tools import TOOL_SCHEMAS, execute_tool


class LLMClient:
    def __init__(
        self,
        model: str = None,
        temperature: float = None,
        enable_search: bool = False
    ):
        # 检查 API Key
        if not settings.dashscope_api_key:
            raise ValueError(
                "未配置 DASHSCOPE_API_KEY 环境变量！\n"
                "请先设置：$env:DASHSCOPE_API_KEY=\"sk-your-api-key\"\n"
                "获取 API Key：https://dashscope.console.aliyun.com/"
            )
        
        self.client = OpenAI(
            api_key=settings.dashscope_api_key,
            base_url=settings.dashscope_base_url
        )
        self.model = model or settings.default_model
        self.temperature = temperature if temperature is not None else settings.default_temperature
        self.enable_search = enable_search
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        max_iterations: int = 5
    ) -> Dict[str, Any]:
        """
        与 LLM 对话，支持 Function Calling 循环
        
        返回：
        {
            "content": str,
            "tool_calls": List[Dict],
            "finish_reason": str
        }
        """
        current_messages = messages.copy()
        all_tool_calls = []
        
        for iteration in range(max_iterations):
            params = {
                "model": self.model,
                "messages": current_messages,
                "temperature": self.temperature
            }
            
            # 通义千问 enable_search 参数
            if self.enable_search:
                params["extra_body"] = {"enable_search": True}
            
            # 添加工具
            if tools:
                params["tools"] = tools
                params["tool_choice"] = "auto"
            
            response = self.client.chat.completions.create(**params)
            choice = response.choices[0]
            message = choice.message
            
            # 添加助手响应到消息历史
            current_messages.append({
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in (message.tool_calls or [])
                ]
            } if message.tool_calls else {
                "role": "assistant",
                "content": message.content or ""
            })
            
            # 检查是否有工具调用
            if not message.tool_calls:
                return {
                    "content": message.content or "",
                    "tool_calls": all_tool_calls,
                    "finish_reason": choice.finish_reason
                }
            
            # 执行工具调用
            for tool_call in message.tool_calls:
                function_name = tool_call.function.name
                try:
                    function_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError as e:
                    # 如果 JSON 解析失败，记录错误并跳过
                    print(f"工具调用参数解析失败: {function_name}")
                    print(f"原始参数: {tool_call.function.arguments}")
                    print(f"错误: {e}")
                    # 尝试清理参数字符串
                    try:
                        # 移除可能的额外空白字符和控制字符
                        cleaned_args = tool_call.function.arguments.strip()
                        function_args = json.loads(cleaned_args)
                    except:
                        # 如果还是失败，使用空字典
                        function_args = {}
                
                # 执行工具
                tool_result = execute_tool(function_name, function_args)
                
                # 记录工具调用
                all_tool_calls.append({
                    "name": function_name,
                    "arguments": function_args,
                    "result": tool_result
                })
                
                # 添加工具响应到消息历史
                current_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": function_name,
                    "content": json.dumps(tool_result, ensure_ascii=False)
                })
        
        # 达到最大迭代次数
        return {
            "content": current_messages[-1].get("content", ""),
            "tool_calls": all_tool_calls,
            "finish_reason": "max_iterations"
        }
    
    def simple_chat(self, messages: List[Dict[str, str]]) -> str:
        """简单对话，不使用工具"""
        result = self.chat(messages, tools=None)
        return result["content"]
