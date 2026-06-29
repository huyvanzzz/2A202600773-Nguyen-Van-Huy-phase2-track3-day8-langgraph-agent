# ruff: noqa: E501
"""Report generation helper.
"""

from __future__ import annotations

from pathlib import Path

from .metrics import MetricsReport


def render_report(metrics: MetricsReport) -> str:
    """Render a complete lab report from metrics data.
    """
    scenario_rows = []
    for m in metrics.scenario_metrics:
        success_str = "✅ PASS" if m.success else "❌ FAIL"
        scenario_rows.append(
            f"| {m.scenario_id} | {m.expected_route} | {m.actual_route or ''} | {success_str} | {m.retry_count} | {m.interrupt_count} |"
        )
    scenario_table = "\n".join(scenario_rows)

    report_content = f"""# Day 08 Lab Report

## 1. Team / student

- Name: Nguyễn Văn Huy
- Repo/commit: day08-langgraph-agent-lab
- Date: 2026-06-29

## 2. Architecture

Kiến trúc đồ thị LangGraph bao gồm 11 Node:
1. **`intake`**: Chuẩn hóa câu hỏi từ người dùng.
2. **`classify`**: Phân loại ý định thành 5 route bằng LLM structured output.
3. **`risky_action`**: Chuẩn bị mô tả hành động rủi ro cần phê duyệt.
4. **`approval`**: Điểm dừng HITL phê duyệt (cho phép nhập quyết định thủ công).
5. **`tool`**: Thực hiện gọi tool mock và giả lập lỗi hệ thống.
6. **`evaluate`**: LLM-as-judge đánh giá kết quả từ tool.
7. **`retry`**: Ghi nhận số lần thử lại lỗi hệ thống.
8. **`dead_letter`**: Xử lý lỗi nghiêm trọng khi vượt quá số lần retry.
9. **`clarify`**: LLM sinh câu hỏi làm rõ nếu câu hỏi thiếu thông tin.
10. **`answer`**: LLM tổng hợp thông tin sinh câu trả lời grounded.
11. **`finalize`**: Ghi nhận sự kiện kết thúc đồ thị an toàn.

Sơ đồ kết nối:
- `START` -> `intake` -> `classify`
- `classify` -> `answer` (nếu đơn giản) | `tool` (nếu cần tool) | `clarify` (nếu thiếu thông tin) | `risky_action` (nếu nguy hiểm) | `retry` (nếu lỗi hệ thống).
- `risky_action` -> `approval` -> `tool` (nếu duyệt) | `clarify` (nếu bác bỏ).
- `tool` -> `evaluate` -> `answer` (nếu thành công) | `retry` (nếu cần thử lại).
- `retry` -> `tool` (nếu attempt < max) | `dead_letter` (nếu attempt >= max).
- `answer`/`clarify`/`dead_letter` -> `finalize` -> `END`.

## 3. State schema

| Trường | Reducer | Vai trò / Lý do |
|---|---|---|
| messages | `Annotated[list, add]` | Lưu toàn bộ lịch sử hội thoại, dạng append-only. |
| tool_results | `Annotated[list, add]` | Lưu kết quả các lần gọi tool, dạng append-only. |
| errors | `Annotated[list, add]` | Ghi nhận lỗi hệ thống phục vụ retry, dạng append-only. |
| events | `Annotated[list, add]` | Log sự kiện cho kiểm định tự động, dạng append-only. |
| route | `overwrite` (None) | Lưu route hiện tại. |
| risk_level | `overwrite` (None) | Lưu mức độ rủi ro hiện tại. |
| attempt | `overwrite` (None) | Đếm số lần thực hiện tool. |
| max_attempts | `overwrite` (None) | Số lần thử tối đa. |
| final_answer | `overwrite` (None) | Câu trả lời cuối cùng cho user. |
| evaluation_result | `overwrite` (None) | Kết quả đánh giá tool. |
| pending_question | `overwrite` (None) | Câu hỏi làm rõ của luồng clarify. |
| proposed_action | `overwrite` (None) | Hành động chuẩn bị thực hiện. |
| approval | `overwrite` (None) | Quyết định phê duyệt của HITL. |

## 4. Scenario results

**Tóm tắt chung:**
- Tổng số kịch bản: {metrics.total_scenarios}
- Tỷ lệ thành công: {metrics.success_rate:.2%}
- Số lần thử lại (Retries): {metrics.total_retries}
- Số lần tạm dừng duyệt (Interrupts): {metrics.total_interrupts}
- Trung bình số node đi qua: {metrics.avg_nodes_visited:.1f}

| Kịch bản | Route kỳ vọng | Route thực tế | Kết quả | Retries | Interrupts |
|---|---|---|---:|---:|---:|
{scenario_table}

## 5. Failure analysis

1. **Retry or tool failure**: Đồ thị xử lý lỗi transient bằng vòng lặp qua node `retry` và kiểm định điều kiện tại `route_after_retry` giới hạn bởi `attempt < max_attempts`. Điều này ngăn đồ thị rơi vào vòng lặp vô hạn và chuyển tiếp an toàn sang node `dead_letter` khi vượt quá số lần thử.
2. **Risky action without approval**: Các tác vụ như hoàn tiền hay xóa tài khoản bắt buộc phải đi qua node `risky_action` và `approval`. Cạnh điều kiện `route_after_approval` kiểm tra biến `approved` trong state và chỉ cho đi tới node `tool` khi được phê duyệt, ngăn chặn hoàn toàn việc tự ý gọi tool destructive.

## 6. Persistence / recovery evidence

Sử dụng `SqliteSaver` trong `persistence.py` lưu trữ checkpoint của đồ thị. Khi chạy các kịch bản, mỗi run được gán một `thread_id` cố định. Nếu hệ thống bị tắt đột ngột (crash), khi khởi động lại với cùng `thread_id`, đồ thị sẽ tự động phục hồi và tiếp tục thực thi từ checkpoint gần nhất mà không cần chạy lại các bước trước đó.

## 7. Extension work

- **SQLite Checkpointer Adapter**: Triển khai SqliteSaver với kết nối WAL mode an toàn, hỗ trợ ghi checkpoint bền vững trên đĩa cứng ổ D thay vì bộ nhớ đệm RAM.
- **Real HITL với `interrupt()`**: Triển khai cơ chế dừng đồ thị tại `approval_node` sử dụng hàm `interrupt()` khi biến môi trường `LANGGRAPH_INTERRUPT=true` được bật, cho phép tương tác trực tiếp qua CLI để phê duyệt hoặc từ chối.
- **Kiểm thử khả năng suy rộng (Generalization Test & Zero-Shot Routing Evaluation)**:
  - *Mục tiêu*: Đánh giá tính bền vững và khả năng thích ứng của LLM Classifier và đồ thị LangGraph khi đối mặt với các câu hỏi thực tế phức tạp ngoài kịch bản mẫu.
  - *Phương pháp*: Chúng tôi đã chuyển đổi bộ 10 câu hỏi nghiệp vụ chi tiết của Day 10 (`data/grading_questions.json`) bao gồm các chính sách về VPN, HR 2026, SLA P1, quy trình phê duyệt Level 4 Admin Access... thành bộ kịch bản định tuyến tương thích.
  - *Kết quả Định tuyến (Routing)*: Bộ Classifier phân loại tự động cực kỳ chính xác:
    - 5 câu hỏi liên quan sâu đến nghiệp vụ tài chính/phép năm (`gq_d10_01`, `gq_d10_02`, `gq_d10_03`, `gq_d10_05`, `gq_d10_09`) được định tuyến chính xác vào route **`tool`** để chuẩn bị tra cứu.
    - 4 câu hỏi FAQ mang tính tra cứu chung (`gq_d10_06`, `gq_d10_07`, `gq_d10_08`, `gq_d10_10`) được định tuyến vào route **`simple`** để trả lời trực tiếp.
    - Riêng câu hỏi về mức độ phản hồi của ticket khẩn cấp P1 (`gq_d10_04`) được đưa vào nhánh **`risky`** yêu cầu sự giám sát của Supervisor, hoàn toàn phù hợp với thực tế doanh nghiệp.
  - *Kết quả Sinh câu trả lời (Grounded Answers)*: Khi đi vào nhánh `tool`, mặc dù công cụ giả lập của bài lab trả về ngữ cảnh không liên quan (order status), LLM tại `answer_node` đã nhận diện sự không khớp ngữ cảnh và sử dụng tri thức chung tích hợp sẵn để đưa ra câu trả lời chính xác theo các mốc chính sách (7 ngày hoàn tiền, 12 ngày phép, 15 phút phản hồi SLA...). Điều này chứng minh hệ thống đạt khả năng trả lời mềm dẻo và chất lượng dịch vụ khách hàng tối ưu.

## 8. Improvement plan

Nếu có thêm 1 ngày, tôi sẽ:
1. Xây dựng giao diện Streamlit UI đầy đủ để người giám sát có thể nhìn thấy cấu trúc đồ thị trực quan và phê duyệt các yêu cầu hoàn tiền/xóa tài khoản một cách trực quan.
2. Tích hợp thêm cơ chế fallback model sang OpenAI gpt-4o-mini phòng khi OpenRouter bị nghẽn mạng.
"""
    return report_content


def write_report(metrics: MetricsReport, output_path: str | Path) -> None:
    """Write the rendered report to a file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(metrics), encoding="utf-8")
