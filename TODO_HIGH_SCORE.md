# Hướng dẫn & Checklist Đạt Điểm Tối Đa (100/100) - Lab Day 08: LangGraph

Tài liệu này tổng hợp toàn bộ các yêu cầu, tiêu chí chấm điểm từ các file hướng dẫn (`README.md`, `LAB_GUIDE.md`, `RUBRIC.md`, `METRICS.md`) và bài giảng (`day08_langgraph_student.pdf`) để giúp bạn hoàn thành bài Lab đạt điểm số cao nhất (Band 90-100 - Production-grade).

---

## 🎯 Mục tiêu điểm số: 90 - 100 điểm
Để đạt mức điểm tối đa, bài làm phải đảm bảo:
1. **Kiến trúc Graph & State** chuẩn hóa, tối ưu, sử dụng đúng Reducer, không rò rỉ hay mất mát dữ liệu.
2. **Tích hợp LLM thực tế** (không dùng hardcode heuristics) cho classification và answer generation.
3. **Luồng Graph hoạt động hoàn hảo** cho cả 7 kịch bản mẫu và các kịch bản ẩn (hidden scenarios) khi chấm điểm.
4. **Cơ chế Persistence (Checkpointing)** hoạt động bền vững với SQLite.
5. **Báo cáo kỹ thuật chi tiết** kèm phân tích lỗi, bảng metrics đầy đủ.
6. **Thực hiện ít nhất 1-2 tính năng mở rộng (Extensions)** ở mức độ hoàn thiện tốt.

---

## 📋 Checklist công việc chi tiết theo từng hạng mục

### 1. Kiến trúc & Thiết kế State (`state.py`) — [15-20 Điểm]
- [ ] **Khai báo đầy đủ các trường bổ sung**: Thêm các trường sau vào `AgentState` trong [state.py](file:///d:/Vin/2A202600773-Nguyen-Van-Huy-phase2-track3-day8-langgraph-agent/src/langgraph_agent_lab/state.py):
  - `evaluation_result` (str): Kết quả đánh giá tool để định tuyến vòng lặp (e.g., `"success"` hoặc `"needs_retry"`).
  - `pending_question` (str): Câu hỏi làm rõ thông tin gửi cho user khi thiếu dữ liệu.
  - `proposed_action` (str): Mô tả hành động rủi ro cao chuẩn bị thực hiện cần duyệt.
  - `approval` (ApprovalDecision hoặc dict): Trạng thái duyệt HITL (approved, reviewer, comment).
- [ ] **Thiết lập Reducer chính xác**:
  - Các trường dạng **Append-only** (phải dùng `Annotated[list, add]`): `messages`, `tool_results`, `errors`, `events`.
  - Các trường dạng **Overwrite** (không dùng reducer, mặc định đè): `route`, `risk_level`, `attempt`, `max_attempts`, `final_answer`, `evaluation_result`, `pending_question`, `proposed_action`, `approval`.
- [ ] **State tinh gọn (Lean & Serializable)**: Không lưu trữ tài liệu lớn hoặc dữ liệu nhị phân trực tiếp trong state. Chỉ lưu ID/references để tối ưu bộ nhớ checkpoint.

### 2. Tích hợp LLM thực thụ (`llm.py`, `nodes.py`) — [15 Điểm]
- [ ] **Cấu hình biến môi trường**: Sao chép `.env.example` thành `.env`, điền API key (`GEMINI_API_KEY`, `OPENAI_API_KEY`, hoặc `ANTHROPIC_API_KEY`).
- [ ] **`classify_node` bắt buộc dùng LLM**:
  - Sử dụng `.with_structured_output(...)` với Pydantic Model để ép LLM trả về chính xác enum route: `simple`, `tool`, `missing_info`, `risky`, `error`.
  - Thiết lập prompt rõ ràng để phân loại chính xác dựa trên độ ưu tiên: `risky` > `tool` > `missing_info` > `error` > `simple`.
  - Đặt `risk_level` tương ứng (`"high"` cho risky, `"low"` cho các route khác).
  - **CẢNH BÁO**: Tuyệt đối không dùng so khớp từ khóa (keyword heuristics) để phân loại. Sẽ bị kiểm tra bằng các kịch bản ẩn khác.
- [ ] **`answer_node` bắt buộc dùng LLM**:
  - LLM phải sinh câu trả lời được liên kết (grounded) từ thông tin trong `tool_results` hoặc ngữ cảnh thực tế, không dùng câu trả lời cứng (hardcoded strings).
- [ ] **Tối ưu `evaluate_node` bằng LLM-as-judge (Bonus)**:
  - Sử dụng LLM để đánh giá kết quả từ tool xem đã hợp lệ chưa (trả về `"success"` hoặc `"needs_retry"`). Heuristic đơn giản (ví dụ tìm chữ `"ERROR"`) chỉ đủ điểm nền tảng.

### 3. Xây dựng và Wiring Graph (`graph.py`, `routing.py`) — [35-40 Điểm]
- [ ] **Đăng ký đúng 11 Node**: Trong [graph.py](file:///d:/Vin/2A202600773-Nguyen-Van-Huy-phase2-track3-day8-langgraph-agent/src/langgraph_agent_lab/graph.py), đăng ký các node với tên định danh tương ứng:
  1. `"intake"`
  2. `"classify"`
  3. `"answer"`
  4. `"tool"`
  5. `"evaluate"`
  6. `"clarify"` (đăng ký cho `ask_clarification_node`)
  7. `"risky_action"`
  8. `"approval"` (đăng ký cho `approval_node`)
  9. `"retry"` (đăng ký cho `retry_or_fallback_node`)
  10. `"dead_letter"`
  11. `"finalize"`
- [ ] **Nối các cạnh cố định (Fixed Edges)**:
  - `START` → `"intake"` → `"classify"`
  - `"tool"` → `"evaluate"`
  - `"answer"` → `"finalize"` → `END`
  - `"clarify"` → `"finalize"` → `END`
  - `"dead_letter"` → `"finalize"` → `END`
- [ ] **Cài đặt các hàm routing trong `routing.py` và liên kết làm cạnh điều kiện (Conditional Edges)**:
  - `route_after_classify`:
    - `"simple"` → `"answer"`
    - `"tool"` → `"tool"`
    - `"missing_info"` → `"clarify"`
    - `"risky"` → `"risky_action"`
    - `"error"` → `"retry"`
  - `route_after_evaluate`:
    - `"needs_retry"` → `"retry"`
    - Ngược lại → `"answer"`
  - `route_after_retry` (Phải giới hạn số lần retry để tránh lặp vô hạn):
    - `attempt < max_attempts` → `"tool"`
    - `attempt >= max_attempts` → `"dead_letter"`
  - `route_after_approval`:
    - Approved → `"tool"`
    - Rejected/Failed → `"clarify"` (hoặc trả thông báo lỗi tùy thiết kế của bạn)
- [ ] **Đảm bảo mọi luồng kếtthuật tại `finalize` → `END`**: Không được để sót bất kỳ luồng rẽ nhánh nào bị treo lơ lửng.

### 4. Persistence & Khôi phục lỗi (`persistence.py`) — [10-15 Điểm]
- [ ] **Triển khai SQLite checkpointer**:
  - Cài đặt thư viện: `pip install langgraph-checkpoint-sqlite`.
  - Trong [persistence.py](file:///d:/Vin/2A202600773-Nguyen-Van-Huy-phase2-track3-day8-langgraph-agent/src/langgraph_agent_lab/persistence.py), sử dụng `SqliteSaver` kết hợp kết nối `sqlite3.connect` và kích hoạt chế độ **WAL mode** (`PRAGMA journal_mode=WAL;`).
  - **Lưu ý**: Phiên bản LangGraph mới yêu cầu khởi tạo dạng `SqliteSaver(conn=sqlite3.connect(...))`, không dùng hàm `from_conn_string`.
- [ ] **Cung cấp Thread ID riêng biệt** cho mỗi phiên chạy trong CLI/Scenarios để lưu trữ phân biệt lịch sử trạng thái.

### 5. Metrics & Kiểm thử tự động (`metrics.py`, `report.py`) — [15-20 Điểm]
- [ ] **Kiểm tra đo lường trong node**:
  - Khi lưu log sự kiện qua `make_event`, tham số đầu tiên `node` phải đặt chính xác là `"retry"` trong `retry_or_fallback_node`, và `"approval"` trong `approval_node`. Bộ quét metrics sẽ tìm kiếm chính xác các chuỗi này để tính toán `retry_count` và `interrupt_count`.
- [ ] **Chạy thành công toàn bộ test scenarios**:
  - Chạy lệnh `make run-scenarios` để chạy qua 7 kịch bản của file `data/sample/scenarios.jsonl`.
  - File `outputs/metrics.json` được sinh ra phải đúng cấu trúc của Pydantic model `MetricsReport`.
- [ ] **Vượt qua các bước xác thực**:
  - Chạy `make test` đạt kết quả pass 100%.
  - Chạy `make grade-local` xác thực thành công file metrics.

### 6. Báo cáo kỹ thuật (`reports/lab_report.md`) — [10-15 Điểm]
- [ ] **Hoàn thiện báo cáo dựa trên template**:
  - Tạo file `reports/lab_report.md` từ [reports/lab_report_template.md](file:///d:/Vin/2A202600773-Nguyen-Van-Huy-phase2-track3-day8-langgraph-agent/reports/lab_report_template.md).
  - Điền đầy đủ thông tin: Kiến trúc đồ thị (Architecture diagram dùng Mermaid), bảng State Schema chi tiết, kết quả của từng scenario từ `metrics.json`.
  - Phân tích cụ thể tối thiểu 2 lỗi hệ thống tiềm ẩn (Transient failure retry & Bypass approval).
  - Nêu rõ giải pháp/kế hoạch cải tiến hệ thống nếu có thêm thời gian phát triển.

### 7. Hạng mục nâng cao (Extensions) — [Bắt buộc ít nhất 1 mục để đạt 90+ điểm]
*Hãy chọn thực hiện tối thiểu một trong các mục sau và cung cấp minh chứng cụ thể trong báo cáo:*
- [ ] **Real HITL (Human-in-the-loop) thực tế**: Sử dụng hàm `interrupt()` của LangGraph trong `approval_node` khi `LANGGRAPH_INTERRUPT=true`. Đồ thị sẽ tạm dừng hoạt động và chờ lệnh `Command(resume=...)` từ người dùng qua terminal/UI để chạy tiếp.
- [ ] **Streamlit UI**: Xây dựng một giao diện nhỏ bằng Streamlit hiển thị trực quan trạng thái đồ thị và cung cấp nút bấm Approve/Reject để tương tác trực tiếp với các tác vụ risky.
- [ ] **Time Travel / Replay**: Minh họa chức năng lấy lịch sử checkpoint thông qua `get_state_history()` và kích hoạt chạy lại (replay) từ một bước trước đó với dữ liệu đầu vào đã được chỉnh sửa.
- [ ] **Crash Recovery Test**: Tạo kịch bản mô phỏng tiến trình của agent bị kill đột ngột giữa chừng (ví dụ khi đang đợi approval), sau đó khởi động lại với cùng `thread_id` để kiểm tra khả năng khôi phục nguyên vẹn và chạy tiếp từ checkpoint.
- [ ] **Parallel Fan-out**: Thiết lập đồ thị chạy song song nhiều tool call đồng thời bằng cơ chế `Send()` của LangGraph nhằm tăng hiệu năng.
- [ ] **Trực quan hóa đồ thị**: Xuất biểu đồ Mermaid của đồ thị ra ảnh hoặc định dạng text hiển thị trong báo cáo bằng hàm `graph.get_graph().draw_mermaid()`.

---

## ⚠️ Các lỗi thường gặp (Common Pitfalls) cần tránh

1. **Quên Khai Báo Reducer**: Nếu 2 node cùng ghi đè lên các trường danh sách như `messages` hay `tool_results` mà không khai báo `Annotated[list, add]`, thông tin của các node trước sẽ bị ghi đè hoàn toàn.
2. **Vòng lặp vô hạn (Unbounded Retry)**: Trong hàm routing `route_after_retry`, nếu không so sánh `attempt < max_attempts` mà luôn định tuyến lại về `"tool"`, đồ thị sẽ lặp vô hạn khi gặp lỗi hệ thống liên tục.
3. **Hardcode Scenario Routing**: Tuyệt đối không viết code rẽ nhánh dựa vào so khớp chuỗi tĩnh của câu hỏi (e.g. `if "reset my password" in query:`). Bài thi chấm điểm sẽ chạy trên các câu hỏi ẩn khác và bạn sẽ bị trừ 15 điểm nếu vi phạm.
4. **Sai tên gọi của Node**: Bộ chấm điểm tự động dựa trên tên node `"retry"` và `"approval"` trong nhật ký sự kiện `events` để đếm số lần chạy thử và phê duyệt. Hãy đảm bảo việc tạo event sử dụng đúng tên node này.
5. **Sai cú pháp khởi tạo `SqliteSaver`**: Trong phiên bản LangGraph mới, cú pháp đúng là `SqliteSaver(conn=sqlite3.connect(...))`, không dùng hàm `from_conn_string`.
