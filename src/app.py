"""VinBus ReAct application: Thought -> Action -> Observation -> Final Answer."""

import json
import os
import sys
import time
from typing import Any, Dict, List

from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mcp_server import MCPAcademicServer
from prompts import CHATBOT_BASELINE_PROMPT, MAX_ITERATIONS, REACT_AGENT_SYSTEM_PROMPT
from providers import get_llm_provider

load_dotenv()


def load_test_cases() -> List[Dict[str, Any]]:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config", "test_cases.json")
    if not os.path.exists(config_path):
        config_path = os.path.join(base_dir, "config", "test_cases.example.json")
    with open(config_path, "r", encoding="utf-8") as file:
        cases = json.load(file)
    if not isinstance(cases, list):
        raise ValueError("config/test_cases.json phải là một JSON array.")
    return cases


def save_waterfall_trace(trace_data: List[Dict[str, Any]]) -> str:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    trace_path = os.path.join(base_dir, "docs", "trace_waterfall.json")
    with open(trace_path, "w", encoding="utf-8") as file:
        json.dump(trace_data, file, ensure_ascii=False, indent=2)
    print(f"📊 [TRACE]: Đã lưu {len(trace_data)} sự kiện tại '{trace_path}'.")
    return trace_path


def run_baseline_chatbot(user_query: str, provider) -> str:
    """Starter chatbot path retained for comparison with the agent."""
    response = provider.generate(user_query, system_prompt=CHATBOT_BASELINE_PROMPT)
    print(f"\n💬 [CHATBOT BASELINE]\n{response}")
    return response


def _context_prompt(user_query: str, observations: List[Dict[str, Any]]) -> str:
    return (
        f"{user_query}\n\nREACT_CONTEXT\n"
        f"Original query: {user_query}\n"
        f"Observation history:\n{json.dumps(observations, ensure_ascii=False)}"
    )


def _render_observation(observation: Dict[str, Any]) -> str:
    status = observation.get("status")
    if status == "SUCCESS" and observation.get("registration_id"):
        return (
            f"Đăng ký vé tháng thành công. Mã đăng ký: {observation['registration_id']}; "
            f"khách hàng: {observation.get('customer_name', '')}; tuyến: {observation.get('route_id', '')}; "
            f"hiệu lực từ {observation.get('valid_from', '')} đến {observation.get('valid_until', '')}."
        )
    if status == "SUCCESS" and observation.get("route_id"):
        stops = " → ".join(observation.get("stops", []))
        frequency = observation.get("frequency_minutes")
        frequency_text = f"{frequency} phút" if frequency is not None else "chưa có dữ liệu live"
        return (
            f"Tuyến {observation['route_id']}: {observation.get('origin', '')} → "
            f"{observation.get('destination', '')}; điểm dừng: {stops}; "
            f"giờ hoạt động: {observation.get('operating_hours', 'không có trong observation')}; "
            f"tần suất: {frequency_text}."
        )
    if status == "SUCCESS" and observation.get("data"):
        return f"Tool trả về dữ liệu: {json.dumps(observation, ensure_ascii=False)}"
    return observation.get("message") or observation.get("error") or json.dumps(
        observation, ensure_ascii=False
    )


def _build_final_answer(observations: List[Dict[str, Any]], candidate: str) -> str:
    if not observations:
        return candidate
    failed = next((item for item in observations if item.get("status") != "SUCCESS"), None)
    if failed:
        return _render_observation(failed)
    return " ".join(_render_observation(item) for item in observations)


def run_react_agent(user_query: str, provider, mcp_server: MCPAcademicServer) -> List[Dict[str, Any]]:
    """Run a bounded ReAct loop and obtain every tool result through MCP."""
    print(f"\n🤖 [REACT AGENT] Câu hỏi: {user_query}")
    trace_logs: List[Dict[str, Any]] = []
    observations: List[Dict[str, Any]] = []
    prompt = user_query
    tools_list = mcp_server.list_tools()

    for step in range(1, MAX_ITERATIONS + 1):
        started = time.perf_counter()
        llm_response = provider.generate_with_tools(
            prompt, tools_list, system_prompt=REACT_AGENT_SYSTEM_PROMPT
        )
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        thought = llm_response.get("thought", "Đang suy luận...")
        response_type = llm_response.get("type")
        print(f"\n--- ReAct step {step}/{MAX_ITERATIONS} ---")
        print(f"🧠 Thought: {thought}")

        if response_type == "text":
            final_answer = _build_final_answer(
                observations, llm_response.get("content", "")
            )
            print(f"🏁 Final Answer: {final_answer}")
            trace_logs.append(
                {
                    "step": step,
                    "query": user_query,
                    "thought": thought,
                    "action_type": "FINAL_ANSWER",
                    "tool_name": None,
                    "arguments": {},
                    "observation": observations[-1] if observations else {},
                    "output": final_answer,
                    "latency_ms": latency_ms,
                }
            )
            return trace_logs

        if response_type != "tool_call":
            error = {"status": "EXECUTION_ERROR", "message": "Provider trả về response không hợp lệ."}
            observations.append(error)
            trace_logs.append(
                {
                    "step": step,
                    "query": user_query,
                    "thought": thought,
                    "action_type": "FINAL_ANSWER",
                    "tool_name": None,
                    "arguments": {},
                    "observation": error,
                    "output": _render_observation(error),
                    "latency_ms": latency_ms,
                }
            )
            return trace_logs

        tool_name = llm_response.get("tool_name")
        arguments = llm_response.get("arguments") or {}
        print(f"🛠️ Action: {tool_name}({arguments})")
        mcp_response = mcp_server.call_tool(tool_name, arguments)
        observation = mcp_response.get("result")
        if not isinstance(observation, dict):
            observation = {"status": "EXECUTION_ERROR", "message": "MCP result không hợp lệ."}
        observations.append(observation)
        print(f"👁️ Observation: {json.dumps(observation, ensure_ascii=False)}")
        trace_logs.append(
            {
                "step": step,
                "query": user_query,
                "thought": thought,
                "action_type": "TOOL_EXECUTION",
                "tool_name": tool_name,
                "arguments": arguments,
                "observation": observation,
                "output": "",
                "latency_ms": latency_ms,
            }
        )

        # The next provider call receives the exact MCP observation.
        prompt = _context_prompt(user_query, observations)

    final_answer = _build_final_answer(
        observations, "Đã đạt giới hạn số bước xử lý an toàn của Agent."
    )
    trace_logs.append(
        {
            "step": MAX_ITERATIONS + 1,
            "query": user_query,
            "thought": "Đạt MAX_ITERATIONS nên dừng để tránh vòng lặp vô hạn.",
            "action_type": "FINAL_ANSWER",
            "tool_name": None,
            "arguments": {},
            "observation": observations[-1] if observations else {},
            "output": final_answer,
            "latency_ms": 0.0,
        }
    )
    return trace_logs


def _called_tools(trace: List[Dict[str, Any]]) -> List[str]:
    return [event["tool_name"] for event in trace if event.get("action_type") == "TOOL_EXECUTION"]


if __name__ == "__main__":
    print("==========================================================")
    print("🚌 VINBUS CUSTOMER SERVICE - REACT AGENT LAB")
    print("==========================================================")
    provider = get_llm_provider()
    mcp_server = MCPAcademicServer()
    print(f"🔌 LLM Provider: {provider.__class__.__name__}")
    print(f"🌐 MCP Server: {mcp_server.server_name}\n")
    tests = load_test_cases()
    print(f"✅ Đã tải {len(tests)} test case.")

    if "--interactive" in sys.argv:
        while True:
            try:
                user_input = input("👤 Bạn hỏi (exit để thoát): ").strip()
                if not user_input or user_input.lower() in {"exit", "quit"}:
                    break
                save_waterfall_trace(run_react_agent(user_input, provider, mcp_server))
            except (KeyboardInterrupt, EOFError):
                break
    elif "--all" in sys.argv:
        all_traces: List[Dict[str, Any]] = []
        completed = 0
        for test_case in tests:
            print(f"\n🧪 [{test_case['id']}] {test_case['question']}")
            if "TODO" in test_case.get("question", ""):
                print("❌ Test case còn TODO.")
                continue
            trace = run_react_agent(test_case["question"], provider, mcp_server)
            all_traces.extend(trace)
            completed += 1
            print(f"✅ Tool calls: {_called_tools(trace) or 'không có'}")
        trace_path = save_waterfall_trace(all_traces)
        print(f"\n📊 KẾT QUẢ: {completed}/{len(tests)} test case đã chạy.")
        print(f"📄 Trace: {trace_path}")
    else:
        print("Dùng --all để chạy 5 test case hoặc --interactive để trò chuyện.")
