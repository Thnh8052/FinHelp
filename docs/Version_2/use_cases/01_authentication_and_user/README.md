# Phân hệ 1: Xác thực & Quản lý Người dùng (Authentication & User Management)

> **Mã phân hệ:** `MOD-AUTH`  
> **Tác nhân tham gia:** `User` (Người dùng), `Admin` (Quản trị viên), `System` (Hệ thống xác thực JWT)

---

## 1. Biểu đồ Phân rã Use Case (Use Case Decomposition Diagram)

```mermaid
flowchart LR
  User(["👤 Người dùng (User)"])
  Admin(["🛡️ Quản trị viên (Admin)"])
  System(["🤖 Hệ thống Xác thực"])

  subgraph AuthScope ["Phân hệ Xác thực Tài khoản"]
    UC_Login(["UC-AUTH-01: Đăng nhập"])
    UC_Register(["UC-AUTH-02: Đăng ký"])
    UC_Profile(["UC-AUTH-03: Xem & Cập nhật hồ sơ"])
    UC_ResetPass(["UC-AUTH-04: Quên / Đặt lại mật khẩu"])
    UC_TokenValidate(["Xác thực Bearer JWT"])
  end

  User --> UC_Login
  User --> UC_Register
  User --> UC_Profile
  User --> UC_ResetPass

  Admin --> UC_Login
  Admin --> UC_Profile

  UC_Login -.->|<<include>>| UC_TokenValidate
  UC_Profile -.->|<<include>>| UC_TokenValidate
  System -.->|Ký & Giải mã Token| UC_TokenValidate
```

---

## 2. Bảng Đặc tả Chi tiết Các Use Case

### Bảng 2.1: Đặc tả Use Case "UC-AUTH-01: Đăng nhập hệ thống"

| Thuộc tính | Nội dung chi tiết |
|---|---|
| **Mã Use Case** | `UC-AUTH-01` |
| **Tên Use Case** | Đăng nhập hệ thống (User Login) |
| **Tác nhân** | Người dùng (`User`), Quản trị viên (`Admin`), Hệ thống (`System`) |
| **Mô tả** | Người dùng gửi thông tin định danh (email/username) và mật khẩu để xác thực quyền truy cập vào hệ thống FinHelp. |
| **Điều kiện tiên quyết** | Người dùng đã có tài khoản hợp lệ được lưu trong cơ sở dữ liệu `users` của MongoDB. |
| **Điều kiện sau** | Hệ thống cấp Access Token (JWT Bearer) có thời hạn, người dùng được chuyển vào màn hình Workspace hoặc Admin Dashboard tương ứng với vai trò. |
| **Luồng sự kiện chính (Main Flow)** | 1. Người dùng bấm nút "Sign in" trên thanh Navbar của Landing Page.<br>2. Giao diện hiển thị Modal Đăng nhập.<br>3. Người dùng nhập Email (hoặc Username) và Mật khẩu, sau đó bấm "Đăng nhập".<br>4. Hệ thống kiểm tra tài khoản trong bảng `users`, mã hóa và so khớp mật khẩu bằng hàm băm `bcrypt`.<br>5. Hệ thống kiểm tra cờ `is_active = True`.<br>6. Hệ thống tạo chuỗi JWT Access Token chứa `user_id`, `role`, `tier` và thời hạn hết hạn (`exp`).<br>7. Hệ thống cập nhật thời gian đăng nhập gần nhất `last_login_at` vào cơ sở dữ liệu.<br>8. Frontend lưu token vào `localStorage`, cập nhật `AuthContext` và điều hướng người dùng vào `/app` (Workspace).<br>9. Hoàn thành Use Case. |
| **Luồng thay thế / Ngoại lệ (Alternative Flows)** | **4a. Thông tin đăng nhập không chính xác:**<br>- Hệ thống trả về mã lỗi `HTTP 401 Unauthorized` kèm thông báo *"Tên đăng nhập hoặc mật khẩu không chính xác"*.<br>- Giao diện hiển thị thông báo lỗi (Toast đỏ), giữ nguyên màn hình để người dùng nhập lại.<br><br>**5a. Tài khoản bị vô hiệu hóa:**<br>- Nếu `is_active = False`, hệ thống từ chối đăng nhập với mã lỗi `HTTP 403 Forbidden` và thông báo *"Tài khoản đã bị tạm khóa bởi quản trị viên"*. |

---

### Bảng 2.2: Đặc tả Use Case "UC-AUTH-02: Đăng ký tài khoản"

| Thuộc tính | Nội dung chi tiết |
|---|---|
| **Mã Use Case** | `UC-AUTH-02` |
| **Tên Use Case** | Đăng ký tài khoản mới (User Registration) |
| **Tác nhân** | Khách vãng lai (`Guest User`), Hệ thống (`System`) |
| **Mô tả** | Người dùng tạo tài khoản mới để lưu trữ các báo cáo tài chính và lịch sử phân tích cá nhân. |
| **Điều kiện tiên quyết** | Email chưa từng được đăng ký trong hệ thống. |
| **Điều kiện sau** | Bản ghi người dùng mới được tạo trong bảng `users`, đồng thời một Notebook mặc định ("Phân tích BCTC Mặc định") được tự động khởi tạo. |
| **Luồng sự kiện chính (Main Flow)** | 1. Người dùng bấm "Get Started" hoặc chuyển sang tab "Đăng ký" trên Auth Modal.<br>2. Người dùng nhập Email, Username, Họ và tên, Mật khẩu (ít nhất 8 ký tự).<br>3. Người dùng bấm nút "Tạo tài khoản".<br>4. Hệ thống kiểm tra định dạng email và tính duy nhất của Email/Username trong cơ sở dữ liệu.<br>5. Hệ thống băm mật khẩu bằng thuật toán `bcrypt` an toàn.<br>6. Hệ thống tạo tài khoản mới với vai trò mặc định `role: "user"`, gói `tier: "free"` kèm hạn mức phân tích (`quota: 50 câu/ngày`).<br>7. Hệ thống tự động tạo một Notebook khởi tạo cho người dùng trong bảng `notebooks`.<br>8. Hệ thống tự động đăng nhập, trả về JWT Access Token.<br>9. Giao diện hiển thị thông báo thành công và chuyển thẳng vào Workspace. |
| **Luồng thay thế / Ngoại lệ** | **4a. Email hoặc Username đã tồn tại:**<br>- Hệ thống trả về `HTTP 400 Bad Request` kèm thông báo cụ thể *"Email đã được sử dụng bởi tài khoản khác"*.<br>**4b. Mật khẩu không đủ mạnh:**<br>- Hệ thống yêu cầu mật khẩu phải có độ dài tối thiểu 8 ký tự và chứa ký tự chữ và số. |

---

## 3. Biểu đồ Tuần tự Luồng Đăng nhập (Sequence Diagram)

```mermaid
sequenceDiagram
  autonumber
  actor User as 👤 Người dùng
  participant UI as 🖥️ Frontend (React SPA)
  participant AuthAPI as 🚪 API Auth (/api/v1/auth/login-json)
  participant Sec as 🛡️ Core Security (Bcrypt & JWT)
  participant DB as 🗄️ MongoDB (Collection: users)

  User->>UI: Nhập Email/Username và Mật khẩu, bấm "Đăng nhập"
  UI->>AuthAPI: POST /api/v1/auth/login-json {identifier, password}
  AuthAPI->>DB: find_one({"$or": [{"email": id}, {"username": id}]})
  alt Không tìm thấy tài khoản
    DB-->>AuthAPI: null
    AuthAPI-->>UI: 401 Unauthorized ("Tài khoản không tồn tại")
    UI-->>User: Hiển thị Toast lỗi đăng nhập
  else Tìm thấy tài khoản
    DB-->>AuthAPI: UserRecord {user_id, password_hash, is_active, role}
    AuthAPI->>Sec: verify_password(password, password_hash)
    alt Mật khẩu sai
      Sec-->>AuthAPI: False
      AuthAPI-->>UI: 401 Unauthorized ("Mật khẩu không chính xác")
      UI-->>User: Hiển thị Toast báo sai mật khẩu
    else Mật khẩu đúng
      Sec-->>AuthAPI: True
      AuthAPI->>Sec: create_access_token(user_id, role, tier)
      Sec-->>AuthAPI: access_token (JWT Bearer)
      AuthAPI->>DB: update_one(user_id, {"$set": {"last_login_at": now}})
      AuthAPI-->>UI: 200 OK {access_token, token_type: "bearer", role, tier}
      UI->>UI: Lưu token vào localStorage & cập nhật AuthContext
      UI-->>User: Chuyển hướng vào Workspace (/app)
    end
  end
```

