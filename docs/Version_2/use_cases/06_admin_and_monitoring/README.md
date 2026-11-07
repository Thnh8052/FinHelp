# Phân hệ 6: Quản trị Hệ thống & Giám sát (Admin & Monitoring Portal)

> **Mã phân hệ:** `MOD-ADMIN`  
> **Tác nhân tham gia:** `Admin` (Quản trị viên hệ thống), `System` (Hệ thống giám sát hạn mức & audit logs)

---

## 1. Biểu đồ Phân rã Use Case (Use Case Decomposition Diagram)

```mermaid
flowchart LR
  Admin(["🛡️ Quản trị viên (Admin)"])
  System(["🤖 Hệ thống FinHelp Core"])
  DB[("🗄️ MongoDB")]

  subgraph AdminScope ["Phân hệ Quản trị & Giám sát Hệ thống"]
    UC_Users(["UC-ADM-01: Quản lý người dùng & Phân vai trò"])
    UC_Quota(["UC-ADM-02: Cấu hình hạn mức Quota & Gói cước"])
    UC_Stats(["UC-ADM-03: Thống kê token & Chi phí LLM"])
    UC_Audit(["UC-ADM-04: Tra cứu nhật ký kiểm toán (Audit Logs)"])
    UC_SysHealth(["UC-ADM-05: Giám sát trạng thái Qdrant & GPU Worker"])
  end

  Admin --> UC_Users
  Admin --> UC_Quota
  Admin --> UC_Stats
  Admin --> UC_Audit
  Admin --> UC_SysHealth

  System -.->|Ghi nhận số token LLM tiêu thụ| UC_Stats
  System -.->|Ghi vết hành động nhạy cảm| UC_Audit
  UC_Users -.->|Cập nhật quyền và trạng thái| DB
```

---

## 2. Bảng Đặc tả Chi tiết Các Use Case

### Bảng 2.1: Đặc tả Use Case "UC-ADM-01: Quản lý người dùng & Phân vai trò"

| Thuộc tính | Nội dung chi tiết |
|---|---|
| **Mã Use Case** | `UC-ADM-01` |
| **Tên Use Case** | Quản lý người dùng & Phân vai trò (User & Role Management) |
| **Tác nhân** | Quản trị viên (`Admin`), Hệ thống (`System`) |
| **Mô tả** | Quản trị viên tra cứu danh sách người dùng, kích hoạt hoặc tạm khóa tài khoản vi phạm, điều chỉnh vai trò (`admin`, `analyst`, `user`) và nâng cấp gói dịch vụ (`free`, `pro`, `enterprise`). |
| **Điều kiện tiên quyết** | Tài khoản thực hiện có vai trò `role = "admin"`. |
| **Điều kiện sau** | Trạng thái tài khoản được cập nhật trong bảng `users`, quyền hạn mới có hiệu lực ngay lập tức trong lần xác thực token tiếp theo. |
| **Luồng sự kiện chính (Main Flow)** | 1. Quản trị viên mở Admin Dashboard từ menu người dùng.<br>2. Hệ thống kiểm tra quyền Admin qua JWT Token (`GET /api/v1/auth/me`).<br>3. Admin Dashboard tải danh sách người dùng qua `GET /api/v1/admin/users`.<br>4. Quản trị viên tìm kiếm người dùng theo email hoặc tên đăng nhập.<br>5. Quản trị viên chọn thay đổi vai trò hoặc gói dịch vụ (ví dụ: cấp gói `pro` cho chuyên viên phân tích).<br>6. Frontend gửi yêu cầu `PATCH /api/v1/admin/users/{user_id}`.<br>7. Hệ thống cập nhật bảng `users` và ghi vết vào `audit_logs`.<br>8. Hiển thị thông báo cập nhật thành công. |
| **Luồng thay thế / Ngoại lệ** | **2a. Không đủ quyền Admin:**<br>- Hệ thống từ chối truy cập với mã `HTTP 403 Forbidden`: *"Bạn không có quyền truy cập vào cổng quản trị"*. |

---

### Bảng 2.2: Đặc tả Use Case "UC-ADM-03: Thống kê token & Chi phí LLM"

| Thuộc tính | Nội dung chi tiết |
|---|---|
| **Mã Use Case** | `UC-ADM-03` |
| **Tên Use Case** | Thống kê token & Chi phí LLM (Token Usage & Cost Monitoring) |
| **Tác nhân** | Quản trị viên (`Admin`), Hệ thống (`System`) |
| **Mô tả** | Quản trị viên theo dõi tổng số lượng token đầu vào (prompt tokens), token đầu ra (completion tokens), số lượt truy vấn BCTC hàng ngày và ước tính chi phí API DeepSeek/OpenAI phát sinh để kiểm soát ngân sách. |
| **Điều kiện tiên quyết** | Tài khoản có quyền `admin`. |
| **Điều kiện sau** | Biểu đồ trực quan và bảng số liệu thống kê được hiển thị đầy đủ trên màn hình quản trị. |
| **Luồng sự kiện chính (Main Flow)** | 1. Quản trị viên chọn tab "Thống kê tài nguyên & Chi phí".<br>2. Frontend gọi `GET /api/v1/admin/stats` kèm bộ lọc thời gian (7 ngày qua, 30 ngày qua).<br>3. Hệ thống tổng hợp dữ liệu từ collection `messages` và các job bóc tách.<br>4. Hiển thị: Tổng số lượt hỏi, Số lượt phát hiện sai lệch số liệu bị chặn bởi `answer_check`, Tổng số token tiêu thụ, Chi phí ước tính theo USD/VND.<br>5. Admin có thể xuất báo cáo thống kê phục vụ nghiệm thu đề tài. |

---

## 3. Biểu đồ Tuần tự Luồng Quản trị Hạn mức (Sequence Diagram)

```mermaid
sequenceDiagram
  autonumber
  actor Admin as 🛡️ Quản trị viên
  participant UI as 🖥️ Admin Dashboard (AdminDashboardModal)
  participant API as 🚪 API Admin (/api/v1/admin)
  participant Sec as 🛡️ Core Security (RBAC Check)
  participant DB as 🗄️ MongoDB (users, audit_logs)

  Admin->>UI: Mở Admin Dashboard -> Tab "Quản lý Người dùng"
  UI->>API: GET /api/v1/admin/users (Bearer Token)
  API->>Sec: require_admin(token)
  Sec-->>API: Quyền hợp lệ (role="admin")
  API->>DB: find({}, {"password_hash": 0}).limit(50)
  DB-->>API: Danh sách tài khoản người dùng
  API-->>UI: 200 OK [users_list]
  UI-->>Admin: Hiển thị bảng danh sách tài khoản kèm hạn mức

  Admin->>UI: Nâng cấp tài khoản user_123 lên Gói "Pro" (quota: 500 câu/ngày)
  UI->>API: PATCH /api/v1/admin/users/user_123 {tier: "pro", quota: {daily_limit: 500}}
  API->>DB: update_one({"user_id": "user_123"}, {"$set": ...})
  API->>DB: insert_one(AuditLogRecord {action: "upgrade_tier", target: "user_123", by: "admin"})
  DB-->>API: Thành công
  API-->>UI: 200 OK {message: "Đã cập nhật hạn mức thành công"}
  UI-->>Admin: Hiển thị Toast thông báo thành công
```

