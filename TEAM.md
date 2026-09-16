# TEAM — Day04, K4-L3B

**Làm nhóm.** Mỗi người tự viết và commit phần INDIVIDUAL của mình.

## Thông tin bài nộp

- Tên nhóm: Tử thần thực tử
- Người đại diện / MSSV: Nguyễn Tiến Lượng — 26A202602378
- Tên repo cần đổi theo mẫu trước khi nộp: `K4-L3-DAY04-NguyenTienLuong-26A202602378-PromptEngineeringToolCalling`
- URL repo hiện tại: https://github.com/Luongday/K4-L3B-Day04-NguyenTienLuong-26A202602378-PromptEngineeringToolCallingLabs
- Nhánh nộp: `main`
- Commit chốt: **TODO — điền SHA sau khi hoàn thành group eval, UI, transcript và report**
- Deadline mặc định: 23:59 ngày 16/09/2026, Asia/Ho_Chi_Minh; chưa có evidence về thông báo đổi hạn.

## Thành viên

| Họ và tên | MSSV | GitHub | Vai trò và công việc | File/commit/PR |
|---|---|---|---|---|
| Nguyễn Tiến Lượng | 26A202602378 | [Luongday](https://github.com/Luongday) | Prompt engineering, tool declaration, chạy eval v0–v3, phân tích safety, web UI và tổng hợp report | `ui.py`, `ui/`, `artifacts/system_prompt.md`, `artifacts/tools.yaml`, `artifacts/version_log.csv`, `runs/`; commits `7844b9d`, `1be2296`, `8b4a214`, `8e886fb`, `ba87a64`, `cc75c97` |

## Nhận xét chung

- Kết quả và bằng chứng: base accuracy tăng từ 0.70 ở v0 lên 0.8667 ở v1 và 1.00 ở v2/v3; group eval đạt 9/10 (0.90); các run dùng làm evidence đều có `provider_error_cases == 0` và `measured_cases == total_cases`. V3 adversarial đạt 8/12 (0.6667), còn bốn lỗi tạo ticket trái phép. Xem `starter_v0/artifacts/version_log.csv` và `starter_v0/runs/`.
- Thay đổi hiệu quả nhất: v2 làm rõ schema/mô tả `clarify`, `search_kb`, `inspect_device`, `lookup_user`, đưa base từ 26/30 lên 30/30.
- Giới hạn còn lại: group case G07 chọn `policy_area="all"` thay vì `data_privacy`; v3 còn thất bại A03/A04/A10/A11; transcript đầu tiên rỗng cần loại khỏi commit evidence; các ticket local sinh ngoài ý muốn cần được dọn trước khi nộp; tên repository hiện tại chưa đúng mẫu; `providers/anthropic_provider.py` còn thay đổi chưa được giải thích.
- Cách phân công và tích hợp: repository hiện ghi nhận một thành viên thực hiện các thay đổi kỹ thuật trên nhánh `main`; mỗi version được lưu bằng run JSON, artifact hash và commit riêng để đối chiếu.

## INDIVIDUAL

Phần dưới đây phải do chính Nguyễn Tiến Lượng tự viết và commit. Nội dung không được AI viết thay hoặc suy diễn từ lịch sử Git.

### Nguyễn Tiến Lượng — 26A202602378

- Phần việc và file/commit/PR: ALL FILE
- Quyết định, khó khăn và cách xử lý: Nothing
- Điều đã học: Nothing
- AI/công cụ đã dùng và cách kiểm tra: Codex
- Thời điểm đã tự nộp URL repo chung trên VLearn: 11:40 
