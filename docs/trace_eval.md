# 📊 BÁO CÁO THU HOẠCH NGHIỆM THU BÀI LAB 3

> **Họ và Tên Học viên:** Nguyễn Ngọc Linh
> **Mã Sinh Viên / Mã Học viên:** 2A202602480
> **Chủ đề:** Trợ lý Dịch vụ Khách hàng VinBus: tra cứu lộ trình tuyến xe bus điện và đăng ký vé tháng.

## 1. Agentic Fit Scoring Matrix

Phạm vi dữ liệu VinBus trong bài là `mock_offline`, được khai báo trong kết quả
tool bằng `data_source`; đây không phải dữ liệu vận hành live của VinBus.

| Tiêu chí | Điểm | Giải trình |
| :--- | :---: | :--- |
| Multi-step Reasoning | 5/5 | TC04 phải tra cứu tuyến trước, đọc route_id từ observation rồi mới đăng ký vé tháng. |
| Tool Interaction | 5/5 | Agent dùng MCP Server để gọi `bus_route_query` và `register_monthly_pass`; dữ liệu được lấy từ mock database. |
| Dynamic Decision | 5/5 | Chỉ đăng ký khi tra cứu trả về `SUCCESS`; với `NOT_FOUND`, Agent dừng và báo đúng lỗi. |
| Long Horizon Goal | 4/5 | Mục tiêu đăng ký được giữ qua nhiều vòng ReAct; bài lab có tối đa 5 bước, chưa triển khai memory dài hạn. |
| **Tổng điểm Agentic Fit** | **19/20** | Chủ đề phù hợp để minh họa ReAct Agent. |

## 2. Tool schema và dữ liệu demo

- `bus_route_query(origin, destination, route_id?)`: trả `route_id`, các điểm dừng, giờ hoạt động, tần suất và `data_source`.
- `register_monthly_pass(customer_name, phone, route_id, start_date)`: trả `registration_id`, trạng thái và thời hạn vé.
- Baseline vẫn giữ `academic_query` và `schedule_appointment`.
- Tuyến hợp lệ trong mock database: `E01`, từ `KĐT Ocean Park` đến `Bến xe Mỹ Đình`.
- Điểm đầu/cuối E01 được đối chiếu với [mạng lưới tuyến VinBus](https://vinbus.vn/gioi-thieu/mang-luoi-tuyen). Danh sách điểm đi qua trong mock được tổng hợp từ [nguồn lộ trình chi tiết do người dùng cung cấp](https://meyreal.com/chi-tiet-lo-trinh-cac-tuyen-xe-buyt-vinbus-ha-noi/); giờ chạy và tần suất được để là chưa có dữ liệu live.

## 3. Kết quả chạy offline/mock

Đã chạy `python src/app.py --all` với đủ **5/5 test case** và tổng cộng **5 lượt gọi tool qua MCP**:

| Test | Kết quả | Chuỗi tool |
| :--- | :--- | :--- |
| TC01 | PASS | Không gọi tool; trả lời trực tiếp và nêu phạm vi mock/offline. |
| TC02 | PASS | `bus_route_query` → `SUCCESS` với `E01`. |
| TC03 | PASS | `register_monthly_pass` → `SUCCESS`, mã `VP-E01-20260915-4567`. |
| TC04 | PASS | `bus_route_query` → `SUCCESS` → `register_monthly_pass` → `SUCCESS`. |
| TC05 | PASS | `bus_route_query` cho Ocean Park → Landmark 81 → `NOT_FOUND`; không đăng ký và không bịa dữ liệu. |

Trace đầy đủ được sinh tại [`docs/trace_waterfall.json`](trace_waterfall.json), gồm 10 sự kiện với các trường query, step, thought, action_type, tool_name, arguments, observation, output và latency_ms.

### Trích đoạn trace thực tế từ TC04

```json
[
  {
    "step": 1,
    "action_type": "TOOL_EXECUTION",
    "tool_name": "bus_route_query",
    "arguments": {
      "origin": "KĐT Ocean Park",
      "destination": "Bến xe Mỹ Đình"
    },
    "observation": {
      "status": "SUCCESS",
      "route_id": "E01",
      "stops": ["KĐT Ocean Park", "Lý Thánh Tông", "Cổ Linh", "Đàm Quang Trung", "Cầu Vĩnh Tuy", "Minh Khai", "Đại La", "Trường Chinh", "Nguyễn Trãi", "Khuất Duy Tiến", "Phạm Hùng", "Bến xe Mỹ Đình"]
    },
    "latency_ms": 0.03
  },
  {
    "step": 2,
    "action_type": "TOOL_EXECUTION",
    "tool_name": "register_monthly_pass",
    "arguments": {
      "customer_name": "Nguyễn Ngọc Linh",
      "phone": "0901234567",
      "route_id": "E01",
      "start_date": "2026-09-15"
    },
    "observation": {
      "status": "SUCCESS",
      "registration_id": "VP-E01-20260915-4567",
      "valid_from": "2026-09-15",
      "valid_until": "2026-10-14"
    },
    "latency_ms": 0.07
  }
]
```

## 4. Tổng kết và giới hạn

- [x] Đã chạy và xác minh chế độ `MockOfflineProvider`.
- [x] Chưa chạy live Gemini/OpenAI vì môi trường chưa cung cấp API key hợp lệ. Không có số liệu live được ghi vào báo cáo.
- [x] Không commit hoặc push tự động; người dùng tự kiểm tra rồi thực hiện thao tác Git nếu cần.
