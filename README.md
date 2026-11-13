# FinHelp

**Trợ lý AI tra cứu và phân tích báo cáo tài chính, có kiểm chứng số liệu.** Tải báo cáo 10-K (PDF) lên một sổ tay, hỏi bằng ngôn ngữ tự nhiên; câu trả lời đi kèm trích dẫn bấm được (nhảy tới trang và tô sáng đúng các dòng trên PDF), và mỗi con số được kiểm lại bằng code trước khi tới tay người dùng.

Đồ án tốt nghiệp, Trường CNTT & TT, ĐHBK Hà Nội. Tác giả: Vũ Thành (MSSV 20225405).

## Khác một công cụ hỏi đáp PDF thông thường ở đâu

- **Kiểm chứng bằng code.** Con số trong câu trả lời phải có trong một đoạn trích đã tìm ra; phép tính viết trong câu trả lời được làm lại bằng bộ tính an toàn; trích dẫn được so với công ty và kỳ báo cáo.
- **Hiểu cả một kho báo cáo.** Mỗi tài liệu được lập danh mục (công ty, loại báo cáo, kỳ); câu hỏi nhiều công ty được lập kế hoạch tìm riêng cho từng tài liệu, kèm lưới an toàn khi kế hoạch chọn thiếu.
- **Biết từ chối.** Một lớp guard nhỏ gắn nhãn an toàn cho mỗi tin nhắn trước khi trả lời (lời khuyên đầu tư, tấn công prompt, ngoài phạm vi, khủng hoảng...).
- **Hội thoại nối tiếp.** "Còn năm 2023?" kế thừa công ty và chỉ tiêu của câu trước. Mỗi sổ tay là một cuộc trò chuyện.
- **Có trang quản trị:** người dùng, tài liệu và tiến trình nạp, dấu vết từng câu trả lời, báo câu trả lời sai số liệu.

Giới hạn đã biết: chủ yếu đo trên báo cáo tiếng Anh (tiếng Việt vẫn chạy nhưng chưa đo); trang PDF quét ảnh hoặc xoay ngang thì không tô sáng được trích dẫn; giới hạn tần suất đang lưu trong bộ nhớ của một tiến trình.

## Kiến trúc tóm tắt

| Phần | Công nghệ |
|---|---|
| Backend | FastAPI, kiểu "modular monolith": 9 module trong `backend/app/modules/` (auth, documents, ingestion, retrieval, query_router, generation, chat, notebooks, admin) |
| Giao diện | React + TypeScript + Vite, PDF.js để xem và tô sáng trích dẫn |
| Dữ liệu | MongoDB (người dùng, sổ tay, tài liệu, tin nhắn, danh mục), Qdrant (vector) |
| Tệp PDF | Ổ đĩa cục bộ hoặc Cloudflare R2 (`STORAGE_BACKEND=local\|r2`) |
| Mô hình chạy cục bộ | BGE-M3 (vector dày và thưa), Qwen3-Reranker, Docling (bóc tách PDF) |
| Mô hình ngôn ngữ | DeepSeek qua API (lập kế hoạch, sinh câu trả lời, guard) |

Luồng một câu hỏi: kiểm tra đầu vào (luật + guard) → chọn tài liệu theo danh mục → tìm kiếm lai và chấm lại → sinh câu trả lời có trích dẫn → kiểm chứng số liệu, phép tính, trích dẫn → trả về từng bước qua SSE.

## Yêu cầu

- Python 3.13, Node.js 22 trở lên, Docker.
- Khóa API DeepSeek (thiếu thì vẫn tìm được đoạn trích nhưng không sinh được câu trả lời).
- GPU NVIDIA khuyến nghị (4 GB VRAM đủ). Không có GPU thì đặt `DEVICE=cpu` (chậm), hoặc trỏ `REMOTE_GPU_URL` tới một máy GPU khác.

## Chạy trên máy của bạn

Các lệnh dưới đây chạy từ thư mục gốc của kho mã. Cần **3 cửa sổ terminal**.

### 1. Hạ tầng: MongoDB và Qdrant

```bash
docker compose up -d mongodb qdrant
```

Chỉ bật hai dịch vụ này. Chưa dùng `docker compose up` trần: ảnh Docker của backend và frontend chưa chạy được (chưa cài thư viện mô hình, chưa có cấu hình nginx). Không dùng `docker compose down -v` (xóa dữ liệu). Cả hai cổng chỉ mở trên `127.0.0.1` và không có mật khẩu: chỉ dùng cho máy cá nhân.

### 2. Backend (cổng 8000)

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
pip install torch --index-url https://download.pytorch.org/whl/cu124   # bản CUDA; bỏ qua nếu chạy CPU
pip install -r requirements-ml.txt
cp .env.example .env
```

Mở `backend/.env` và đặt ít nhất:

| Biến | Ý nghĩa |
|---|---|
| `SECRET_KEY` | **Bắt buộc**, không có thì server không khởi động. Tạo bằng `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `ADMIN_PASSWORD` | Mật khẩu tài khoản `admin` (từ 8 ký tự), được tạo hoặc đặt lại mỗi lần khởi động. Không đặt thì không có admin; đừng để dòng này trống, server sẽ không khởi động |
| `DEEPSEEK_API_KEY` | Khóa gọi mô hình ngôn ngữ |
| `ENVIRONMENT=development` | Chỉ trên máy của bạn: cho phép khóa mẫu và in mã đặt lại mật khẩu ra log khi chưa cấu hình email |

Các biến khác (MongoDB, Qdrant, lưu trữ, mô hình, email) đã có giá trị mặc định đúng với `docker-compose.yml` và được giải thích ngay trong `.env.example`. Muốn thử nhanh với PDF: `PARSER_ENGINE=pymupdf` (nhanh, bảng kém hơn Docling).

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Lần đầu, các mô hình tải từ Hugging Face (nặng, chờ vài phút). Kiểm tra: http://127.0.0.1:8000/health và http://127.0.0.1:8000/docs.

### 3. Frontend (cổng 5173)

```bash
cd frontend
npm install
npm run dev
```

Mở http://localhost:5173. Vite chuyển `/api` sang `127.0.0.1:8000`; cần backend chạy trước.

### 4. Thử luồng chính

1. Đăng ký tài khoản (hoặc đăng nhập `admin` bằng `ADMIN_PASSWORD`).
2. Tạo sổ tay, tải một báo cáo 10-K bằng tiếng Anh và chờ trạng thái chuyển sang "sẵn sàng".
3. Hỏi một câu về số liệu, ví dụ "What was the revenue in FY2023?".
4. Bấm vào trích dẫn: PDF mở đúng trang và tô vàng các dòng được trích.
5. Hỏi nối tiếp: "And in FY2022?".

## Kiểm thử

```bash
cd backend && python -m pytest -q          # test backend, không cần mạng, GPU hay khóa API
cd frontend && npm run build               # kiểm tra kiểu TypeScript và dựng bản build
cd frontend && npm run test:highlight      # test thuật toán tô sáng trích dẫn (Node 22.18+)
```

`npm run test:highlight` chỉ chạy phần kiểm trên trang PDF thật khi bộ dữ liệu thử nghiệm có trên máy; nếu không, nó chạy các ca cố định.

## Cấu trúc thư mục

```
backend/app/modules/   9 module nghiệp vụ
backend/app/core/      cấu hình, bảo mật, mã lỗi
backend/scripts/       công cụ một lần (khởi tạo chỉ mục, chuyển đổi MongoDB V3, kiểm tra kết nối R2...)
backend/tests/         test backend
frontend/src/          giao diện (features/, components/, locales/ en và vi)
docs/Version_2/        lộ trình phát triển, sơ đồ, đặc tả use case
docker-compose.yml     MongoDB và Qdrant cho môi trường phát triển
```

Lộ trình và việc còn lại: [docs/Version_2/DEV_ROADMAP_V2.md](docs/Version_2/DEV_ROADMAP_V2.md).
