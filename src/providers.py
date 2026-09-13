"""Multi-provider adapter with a deterministic offline VinBus provider."""

import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


class BaseLLMProvider:
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        raise NotImplementedError

    def generate_with_tools(
        self,
        prompt: str,
        tools_schema: List[Dict[str, Any]],
        system_prompt: str = "",
    ) -> Dict[str, Any]:
        raise NotImplementedError


class MockOfflineProvider(BaseLLMProvider):
    """Rule-based adapter that mirrors tool calls needed by the five lab tests."""

    def __init__(self):
        self.model_name = "Offline-Mock-Model-2026"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        return (
            f"[Mock Chatbot Response]: Tôi đã nhận câu hỏi '{prompt}'. "
            "Chế độ chatbot không gọi dữ liệu thời gian thực."
        )

    @staticmethod
    def _extract_route(prompt: str) -> tuple[str, str]:
        match = re.search(
            r"từ\s+(.+?)\s+đến\s+(.+?)(?=\s*(?:[.,;]|rồi\b|và\b|$))",
            prompt,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if match:
            return match.group(1).strip(), match.group(2).strip()
        return "", ""

    @staticmethod
    def _extract_registration(prompt: str, route_id: Optional[str]) -> Dict[str, str]:
        name_match = re.search(
            r"(?:cho|của)\s+(?:anh|chị|ông|bà)??\s*([^,.;]+?)\s*,\s*"
            r"(?:số điện thoại|điện thoại|sđt|sdt)",
            prompt,
            flags=re.IGNORECASE,
        )
        phone_match = re.search(r"(?:0\d{9,10}|\+84\d{9,10})", prompt)
        date_match = re.search(r"\b20\d{2}-\d{2}-\d{2}\b", prompt)
        route_match = re.search(r"\b(?:VB|E)\d+\b", prompt, flags=re.IGNORECASE)
        return {
            "customer_name": (name_match.group(1).strip() if name_match else ""),
            "phone": (phone_match.group(0) if phone_match else ""),
            "route_id": (route_id or (route_match.group(0).upper() if route_match else "")),
            "start_date": (date_match.group(0) if date_match else ""),
        }

    @staticmethod
    def _latest_observation(prompt: str) -> Dict[str, Any]:
        marker = "Observation history:"
        if marker not in prompt:
            return {}
        raw = prompt.rsplit(marker, 1)[-1].strip()
        try:
            history = json.loads(raw)
            return history[-1] if isinstance(history, list) and history else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    @staticmethod
    def _is_route_request(prompt_lower: str) -> bool:
        return (
            "lộ trình" in prompt_lower
            or "điểm dừng" in prompt_lower
            or "tra cứu tuyến" in prompt_lower
            or ("tuyến" in prompt_lower and " từ " in prompt_lower and " đến " in prompt_lower)
        )

    def generate_with_tools(
        self,
        prompt: str,
        tools_schema: List[Dict[str, Any]],
        system_prompt: str = "",
    ) -> Dict[str, Any]:
        prompt_lower = prompt.lower()
        observation = self._latest_observation(prompt)
        original_query = prompt.split("\n\nREACT_CONTEXT", 1)[0]
        original_lower = original_query.lower()

        if observation:
            status = observation.get("status")
            if status != "SUCCESS":
                return {
                    "type": "text",
                    "content": observation.get("message") or observation.get("error") or "Không thể tiếp tục do tool trả về lỗi.",
                    "thought": "Observation không thành công nên dừng chuỗi hành động phụ thuộc.",
                }
            if observation.get("registration_id"):
                return {
                    "type": "text",
                    "content": "Đã nhận kết quả đăng ký vé tháng từ tool.",
                    "thought": "Đã có registration_id trong observation, tổng hợp câu trả lời cuối.",
                }
            if observation.get("route_id") and "đăng ký" in original_lower:
                arguments = self._extract_registration(original_query, observation["route_id"])
                return {
                    "type": "tool_call",
                    "tool_name": "register_monthly_pass",
                    "arguments": arguments,
                    "thought": "Tuyến đã hợp lệ trong observation; tiếp tục đăng ký vé tháng bằng route_id đó.",
                }
            return {
                "type": "text",
                "content": "Đã nhận kết quả tra cứu tuyến từ tool.",
                "thought": "Observation tuyến hợp lệ đã đủ để trả lời yêu cầu tra cứu.",
            }

        # Multi-step requests must inspect the route before attempting registration.
        if self._is_route_request(original_lower):
            origin, destination = self._extract_route(original_query)
            return {
                "type": "tool_call",
                "tool_name": "bus_route_query",
                "arguments": {"origin": origin, "destination": destination},
                "thought": "Cần tra cứu tuyến VinBus trước để xác nhận route_id và các điểm dừng.",
            }

        if "đăng ký" in original_lower and "vé tháng" in original_lower:
            arguments = self._extract_registration(original_query, None)
            return {
                "type": "tool_call",
                "tool_name": "register_monthly_pass",
                "arguments": arguments,
                "thought": "Người dùng yêu cầu đăng ký vé tháng với thông tin đã cung cấp.",
            }

        # Preserve the academic baseline branches used by the starter lab.
        student_match = re.search(r"SV\d+", original_query, flags=re.IGNORECASE)
        if student_match and ("học vụ" in original_lower or "tra cứu" in original_lower):
            student_id = student_match.group(0).upper()
            return {
                "type": "tool_call",
                "tool_name": "academic_query",
                "arguments": {"student_id": student_id},
                "thought": f"Gọi academic_query để tra cứu {student_id}.",
            }
        if student_match and "đặt lịch" in original_lower:
            return {
                "type": "tool_call",
                "tool_name": "schedule_appointment",
                "arguments": {
                    "student_id": student_match.group(0).upper(),
                    "datetime_str": "14:00 15/09/2026",
                    "advisor_name": "PGS.TS Nguyễn Văn A",
                },
                "thought": "Gọi schedule_appointment theo thông tin cuộc hẹn.",
            }

        return {
            "type": "text",
            "content": (
                "VinBus trong bài lab hỗ trợ tra cứu tuyến và đăng ký vé tháng. "
                "Dữ liệu vận hành hiện là mock/offline; hãy cung cấp điểm đi, điểm đến "
                "hoặc thông tin đăng ký đầy đủ nếu cần thao tác."
            ),
            "thought": "Câu hỏi chung có thể trả lời trực tiếp, không cần gọi tool.",
        }


class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider with native function calling."""

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gemini-2.5-flash"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            return MockOfflineProvider().generate(prompt, system_prompt)
        try:
            from google import genai

            client = genai.Client(api_key=self.api_key)
            contents = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            response = client.models.generate_content(model=self.model_name, contents=contents)
            return response.text or ""
        except Exception:
            return "[Gemini Error]: Live provider không thể tạo phản hồi."

    def generate_with_tools(self, prompt, tools_schema, system_prompt=""):
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt)
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            declarations = [
                {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {}),
                }
                for tool in tools_schema
                if tool.get("name") and tool.get("parameters")
            ]
            config = types.GenerateContentConfig(
                system_instruction=system_prompt or None,
                tools=[{"function_declarations": declarations}],
                temperature=0.2,
            )
            response = client.models.generate_content(model=self.model_name, contents=prompt, config=config)
            if response.function_calls:
                call = response.function_calls[0]
                args = dict(call.args) if getattr(call, "args", None) else {}
                return {
                    "type": "tool_call",
                    "tool_name": call.name,
                    "arguments": args,
                    "thought": f"Gemini chọn tool {call.name}.",
                }
            return {
                "type": "text",
                "content": response.text or "",
                "thought": "Gemini trả lời trực tiếp.",
            }
        except Exception:
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt)


class OpenAIProvider(BaseLLMProvider):
    """OpenAI provider with native function calling."""

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gpt-4o-mini"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_openai_api_key_here":
            return MockOfflineProvider().generate(prompt, system_prompt)
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key)
            messages = ([{"role": "system", "content": system_prompt}] if system_prompt else [])
            messages.append({"role": "user", "content": prompt})
            response = client.chat.completions.create(model=self.model_name, messages=messages)
            return response.choices[0].message.content or ""
        except Exception:
            return "[OpenAI Error]: Live provider không thể tạo phản hồi."

    def generate_with_tools(self, prompt, tools_schema, system_prompt=""):
        if not self.api_key or self.api_key == "your_openai_api_key_here":
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt)
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key)
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {}),
                    },
                }
                for tool in tools_schema
                if tool.get("name")
            ]
            messages = ([{"role": "system", "content": system_prompt}] if system_prompt else [])
            messages.append({"role": "user", "content": prompt})
            response = client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )
            message = response.choices[0].message
            if message.tool_calls:
                call = message.tool_calls[0]
                args = json.loads(call.function.arguments or "{}")
                return {
                    "type": "tool_call",
                    "tool_name": call.function.name,
                    "arguments": args,
                    "thought": f"OpenAI chọn tool {call.function.name}.",
                }
            return {
                "type": "text",
                "content": message.content or "",
                "thought": "OpenAI trả lời trực tiếp.",
            }
        except Exception:
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt)


def get_llm_provider() -> BaseLLMProvider:
    provider_type = os.getenv("LLM_PROVIDER", "gemini").lower()
    if provider_type == "gemini" and os.getenv("GEMINI_API_KEY") not in (None, "", "your_gemini_api_key_here"):
        return GeminiProvider()
    if provider_type == "openai" and os.getenv("OPENAI_API_KEY") not in (None, "", "your_openai_api_key_here"):
        return OpenAIProvider()
    return MockOfflineProvider()
