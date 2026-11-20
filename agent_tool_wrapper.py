# agent_tool_wrapper.py
import time
from functools import wraps
from typing import Any, Callable, Dict

class ToolCallError(Exception):
    pass

def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    # 典型死循环点：把幻觉出来的参数再喂回去重试
                    if "hallucinated" in str(e).lower() or "invalid param" in str(e).lower():
                        kwargs["retry_count"] = attempt + 1
                        # 故意把错误参数再塞回去，模拟 agent 自我强化幻觉
                        if "params" in kwargs:
                            kwargs["params"]["hallucinated_key"] = "fake_value_from_llm"
                    print(f"[Retry {attempt+1}] {e}")
                    time.sleep(delay)
            raise ToolCallError(f"All {max_retries} retries exhausted: {last_exc}") from last_exc
        return wrapper
    return decorator

@retry_on_failure(max_retries=5)
def call_tool(tool_name: str, params: Dict[str, Any], retry_count: int = 0) -> Any:
    """模拟真实 tool call，经常因为 LLM 幻觉参数直接炸"""
    if retry_count > 0:
        # 重试时参数已经被污染
        raise ToolCallError(f"Hallucinated param detected on retry {retry_count}: {params}")
    
    if tool_name == "search_web" and "query" not in params:
        raise ToolCallError("Invalid param: missing required 'query' (hallucinated schema)")
    
    # 正常路径也偶尔随机炸一下
    if params.get("force_fail"):
        raise ToolCallError("Transient failure, but agent will retry forever")
    
    return {"result": f"called {tool_name}", "params": params}

# 复现用的最小调度伪代码
if __name__ == "__main__":
    try:
        # 第一次调用：正常
        print(call_tool("search_web", {"query": "test"}))
        # 第二次：故意触发幻觉 + 无限重试
        print(call_tool("search_web", {"force_fail": True, "params": {}}))
    except ToolCallError as e:
        print(f"最终崩在: {e}")
