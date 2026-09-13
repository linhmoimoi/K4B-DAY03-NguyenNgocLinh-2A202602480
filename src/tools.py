"""
Tool schemas and deterministic execution backends for the lab.

The VinBus records in this module are intentionally mock/offline data. They
make the ReAct flow reproducible without claiming to be live VinBus data.
"""

from datetime import date, timedelta
import json
import re
from typing import Any, Dict, Optional


TOOLS_SCHEMA = [
    {
        "name": "academic_query",
        "description": "Tra cứu hồ sơ và thông tin học vụ của sinh viên VinUni bằng mã sinh viên.",
        "parameters": {
            "type": "object",
            "properties": {
                "student_id": {
                    "type": "string",
                    "description": "Mã sinh viên cần tra cứu (ví dụ: SV2026001)",
                }
            },
            "required": ["student_id"],
        },
    },
    {
        "name": "schedule_appointment",
        "description": "Đặt lịch hẹn tư vấn học vụ với cố vấn học tập VinUni.",
        "parameters": {
            "type": "object",
            "properties": {
                "student_id": {
                    "type": "string",
                    "description": "Mã sinh viên cần đặt lịch, ví dụ SV2026001.",
                },
                "datetime_str": {
                    "type": "string",
                    "description": "Thời gian hẹn, ví dụ 14:00 15/09/2026.",
                },
                "advisor_name": {
                    "type": "string",
                    "description": "Tên cố vấn học tập.",
                },
            },
            "required": ["student_id", "datetime_str", "advisor_name"],
        },
    },
    {
        "name": "bus_route_query",
        "description": "Tra cứu tuyến xe bus điện VinBus giữa điểm đi và điểm đến trong dữ liệu demo offline.",
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {
                    "type": "string",
                    "description": "Điểm đi cần tra cứu.",
                },
                "destination": {
                    "type": "string",
                    "description": "Điểm đến cần tra cứu.",
                },
                "route_id": {
                    "type": "string",
                    "description": "Mã tuyến tùy chọn nếu người dùng đã biết, ví dụ E01.",
                },
            },
            "required": ["origin", "destination"],
        },
    },
    {
        "name": "register_monthly_pass",
        "description": "Đăng ký vé tháng VinBus cho một tuyến đã được xác nhận trong dữ liệu demo offline.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "Họ tên khách hàng.",
                },
                "phone": {
                    "type": "string",
                    "description": "Số điện thoại liên hệ.",
                },
                "route_id": {
                    "type": "string",
                    "description": "Mã tuyến VinBus hợp lệ, ví dụ E01.",
                },
                "start_date": {
                    "type": "string",
                    "description": "Ngày bắt đầu vé theo định dạng YYYY-MM-DD.",
                },
            },
            "required": ["customer_name", "phone", "route_id", "start_date"],
        },
    },
]


ACADEMIC_DATABASE = {
    "SV2026001": {
        "full_name": "Nguyễn Văn An",
        "class": "AI-K4",
        "gpa": 3.85,
        "email": "an.nv@vinuni.edu.vn",
        "status": "Đang học",
        "advisor": "PGS.TS Nguyễn Văn A",
    },
    "SV2026002": {
        "full_name": "Trần Thị Bình",
        "class": "AI-K4",
        "gpa": 3.60,
        "email": "binh.tt@vinuni.edu.vn",
        "status": "Đang học",
        "advisor": "TS. Lê Thị B",
    },
}


# Mock/offline VinBus data for deterministic lab evaluation. Route E01's public
# endpoints and corridor are based on the VinBus Hà Nội route network; live
# operations such as departure times and frequency are deliberately not claimed.
VINBUS_ROUTES = {
    "E01": {
        "route_id": "E01",
        "origin": "KĐT Ocean Park",
        "destination": "Bến xe Mỹ Đình",
        "stops": [
            "KĐT Ocean Park",
            "Lý Thánh Tông",
            "Cổ Linh",
            "Đàm Quang Trung",
            "Cầu Vĩnh Tuy",
            "Minh Khai",
            "Đại La",
            "Trường Chinh",
            "Nguyễn Trãi",
            "Khuất Duy Tiến",
            "Phạm Hùng",
            "Bến xe Mỹ Đình",
        ],
        "operating_hours": "Chưa tích hợp dữ liệu vận hành thời gian thực",
        "frequency_minutes": None,
        "route_reference": "https://vinbus.vn/gioi-thieu/mang-luoi-tuyen",
        "data_source": "mock_offline_based_on_public_route",
    }
}


def _json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def execute_academic_query(student_id: str) -> str:
    """Tra cứu học vụ theo mã sinh viên (baseline được giữ lại)."""
    normalized_id = str(student_id).strip().upper()
    student = ACADEMIC_DATABASE.get(normalized_id)
    if student:
        return _json({"status": "SUCCESS", "student_id": normalized_id, "data": student})
    return _json(
        {
            "status": "NOT_FOUND",
            "message": f"Không tìm thấy dữ liệu sinh viên có mã '{student_id}'.",
        }
    )


def execute_schedule_appointment(
    student_id: str,
    datetime_str: str,
    advisor_name: str = "PGS.TS Nguyễn Văn A",
) -> str:
    """Đặt lịch hẹn tư vấn học vụ (baseline được giữ lại)."""
    normalized_id = str(student_id).strip().upper()
    if not normalized_id or not str(datetime_str).strip() or not str(advisor_name).strip():
        return _json({"status": "INVALID_ARGUMENT", "message": "Thiếu thông tin đặt lịch."})
    return _json(
        {
            "status": "SUCCESS",
            "booking_id": f"BK-{normalized_id}-99",
            "student_id": normalized_id,
            "datetime": str(datetime_str).strip(),
            "advisor": str(advisor_name).strip(),
            "message": f"Đặt lịch thành công cho sinh viên {normalized_id}.",
        }
    )


def execute_bus_route_query(
    origin: str, destination: str, route_id: Optional[str] = None
) -> str:
    """Tra cứu tuyến VinBus trong cơ sở dữ liệu mock/offline."""
    origin = str(origin).strip()
    destination = str(destination).strip()
    if not origin or not destination:
        return _json(
            {
                "status": "INVALID_ARGUMENT",
                "message": "origin và destination là bắt buộc.",
            }
        )

    if route_id:
        route = VINBUS_ROUTES.get(str(route_id).strip().upper())
        if route is None:
            return _json(
                {
                    "status": "NOT_FOUND",
                    "route_id": str(route_id).strip().upper(),
                    "message": "Không tìm thấy tuyến VinBus trong dữ liệu demo.",
                }
            )
    else:
        route = next(
            (
                item
                for item in VINBUS_ROUTES.values()
                if item["origin"].casefold() == origin.casefold()
                and item["destination"].casefold() == destination.casefold()
            ),
            None,
        )

    if route is None:
        return _json(
            {
                "status": "NOT_FOUND",
                "origin": origin,
                "destination": destination,
                "message": "Không tìm thấy tuyến VinBus phù hợp trong dữ liệu demo offline.",
            }
        )

    return _json({"status": "SUCCESS", **route})


def execute_register_monthly_pass(
    customer_name: str, phone: str, route_id: str, start_date: str
) -> str:
    """Đăng ký vé tháng VinBus cho tuyến đã biết."""
    customer_name = str(customer_name).strip()
    phone = str(phone).strip()
    route_id = str(route_id).strip().upper()
    start_date = str(start_date).strip()

    if not all((customer_name, phone, route_id, start_date)):
        return _json(
            {
                "status": "INVALID_ARGUMENT",
                "message": "customer_name, phone, route_id và start_date là bắt buộc.",
            }
        )
    if not re.fullmatch(r"(?:0\d{9,10}|\+84\d{9,10})", phone):
        return _json({"status": "INVALID_ARGUMENT", "message": "Số điện thoại không hợp lệ."})
    try:
        valid_from = date.fromisoformat(start_date)
    except ValueError:
        return _json(
            {
                "status": "INVALID_ARGUMENT",
                "message": "start_date phải có định dạng YYYY-MM-DD.",
            }
        )

    if route_id not in VINBUS_ROUTES:
        return _json(
            {
                "status": "NOT_FOUND",
                "route_id": route_id,
                "message": "Không thể đăng ký vì route_id không tồn tại trong dữ liệu demo.",
            }
        )

    valid_until = valid_from + timedelta(days=29)
    registration_id = f"VP-{route_id}-{valid_from:%Y%m%d}-{phone[-4:]}"
    return _json(
        {
            "status": "SUCCESS",
            "registration_id": registration_id,
            "customer_name": customer_name,
            "phone": phone,
            "route_id": route_id,
            "valid_from": valid_from.isoformat(),
            "valid_until": valid_until.isoformat(),
            "data_source": "mock_offline",
        }
    )


TOOL_ROUTER = {
    "academic_query": execute_academic_query,
    "schedule_appointment": execute_schedule_appointment,
    "bus_route_query": execute_bus_route_query,
    "register_monthly_pass": execute_register_monthly_pass,
}


def dispatch_tool_call(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Trung chuyển một tool call và luôn trả về JSON hợp lệ."""
    if tool_name not in TOOL_ROUTER:
        return _json(
            {"status": "UNKNOWN_TOOL", "error": f"Tool '{tool_name}' không tồn tại."}
        )
    if not isinstance(arguments, dict):
        return _json({"status": "INVALID_ARGUMENT", "error": "arguments phải là object JSON."})
    try:
        return TOOL_ROUTER[tool_name](**arguments)
    except TypeError as exc:
        return _json({"status": "INVALID_ARGUMENT", "error": str(exc)})
    except Exception as exc:  # pragma: no cover - defensive execution boundary
        return _json({"status": "EXECUTION_ERROR", "error": str(exc)})
