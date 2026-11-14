# Nguyên tắc HAX và PAIR áp vào giao diện FinHelp

> **Cập nhật:** 14/11/2026. Một trang đọc nhanh để chọn việc giao diện (GD-2 và các việc nhỏ), không phải bản nghiên cứu đầy đủ.
> **Nguồn đã đọc:** (1) Amershi và cộng sự, *Guidelines for Human-AI Interaction*, CHI 2019 (Microsoft), bảng 18 nguyên tắc ở trang 3, đọc trực tiếp từ bài báo. (2) Google PAIR, *People + AI Guidebook*, ba chương: Explainability + Trust, Errors + Graceful Failure, Feedback + Controls (đọc bản tóm tắt qua công cụ tải trang, không đọc từng chữ). **Chưa đọc:** thư viện thiết kế HAX (trang không tải được qua công cụ) và chương Mental Models của PAIR.
> **Hiện trạng giao diện** lấy từ `ChatContainer.tsx` và `locales/en.ts`: có bốn giai đoạn tải ("Reading your question…", "Searching the documents…", "Analyzing the figures and writing the answer…", "Checking the answer…") kèm câu báo chậm, dòng "đã hiểu câu hỏi về …" kèm lựa chọn thay thế, nút sao chép, ba câu gợi ý, trích dẫn bấm được và tô sáng trên PDF. **Không tìm thấy** nút đánh giá, nút hỏi lại, nhãn trạng thái `answered`, `partial`, `not_found` trong hai file đó (GD-2 trong lộ trình chưa làm).

## 1. Mười tám nguyên tắc HAX và FinHelp

Có = đã có và thấy trên giao diện hoặc trong câu trả lời; Một phần = có nhưng thiếu một mảnh; Chưa = chưa có; N/A = không áp dụng cho sản phẩm hỏi đáp này.

| # | Nguyên tắc (diễn đạt lại) | FinHelp | Ghi chú |
|---|---|---|---|
| G1 | Nói rõ hệ thống làm được gì | Một phần | Có 3 câu gợi ý và câu trả lời "bạn có thể hỏi gì"; chưa có một dòng nói giới hạn (báo cáo tiếng Anh, hồ sơ SEC, không tư vấn đầu tư) |
| G2 | Nói rõ hệ thống làm tốt tới đâu | Chưa | Không có dấu hiệu độ tin cậy trên giao diện; dữ liệu đã có (trạng thái, dòng "⚠️ chưa kiểm chứng") |
| G3 | Đúng lúc theo ngữ cảnh | Có | Giai đoạn tải thật; báo khi chậm |
| G4 | Hiện thông tin liên quan tới việc đang làm | Có | Trích dẫn [n] bấm được, tô sáng trang PDF, tô đậm dòng chứa con số |
| G5 | Hợp chuẩn mực xã hội | Có | Từ chối lịch sự, trả lời theo ngôn ngữ của câu hỏi |
| G6 | Tránh định kiến | N/A | Dữ liệu là báo cáo tài chính; bộ bảo vệ đã chặn nhóm nhạy cảm |
| G7 | Gọi dùng dễ | Có | `@file` chọn tài liệu, câu gợi ý |
| G8 | Bỏ qua dễ | N/A | Không có gợi ý tự bật |
| G9 | Sửa dễ khi sai | Một phần | Có lựa chọn thay thế dưới dòng "đã hiểu câu hỏi về"; chưa có hỏi lại câu này hay sửa câu hỏi |
| G10 | Thu hẹp khi nghi ngờ | Có | Hỏi lại khi thiếu thông tin, trả lời từng nguồn rồi hỏi, trả lời một phần và nói rõ thiếu gì, và từ 14/11 câu "xin lỗi, vượt quá giới hạn xử lý, hãy chia nhỏ câu hỏi" |
| G11 | Giải thích vì sao hệ thống làm vậy | Một phần | "Đã hiểu câu hỏi về …" và trích dẫn; chưa nói vì sao chọn trang hoặc kỳ này |
| G12 | Nhớ tương tác gần đây | Có | Câu nối tiếp dùng chủ đề và 6 tin nhắn gần nhất |
| G13 | Học theo hành vi người dùng | N/A (cố ý không) | Cá nhân hóa không cần cho đồ án và làm khó kiểm chứng |
| G14 | Cập nhật thận trọng | Có | Prompt và các cờ mới đi sau cờ cấu hình, mặc định giữ bản đã đo (ví dụ v4.1 tắt) |
| G15 | Phản hồi chi tiết từng câu trả lời | Chưa | Chưa có đánh giá hay bình luận |
| G16 | Nói phản hồi dẫn tới gì | Chưa | Phụ thuộc G15 |
| G17 | Điều khiển toàn cục | Một phần | Chọn nguồn của sổ tay là điều khiển hệ thống dùng gì; chưa có tùy chọn khác |
| G18 | Báo khi có thay đổi | Chưa | Không có thông báo thay đổi |

## 2. PAIR: những ý đáng giữ cho sản phẩm tài chính

- **Hiệu chỉnh niềm tin, không tối đa hóa nó.** Người dùng nên dựa vào hệ thống nơi nó đúng và tự kiểm nơi nó yếu. Cảnh báo có thể làm giảm tin một câu nhưng tránh dựa dẫm quá mức. FinHelp đã làm điều này một phần bằng dòng "⚠️ số chưa kiểm chứng được" và câu "chưa hoàn tất".
- **Giải thích theo mức rủi ro.** Số liệu tài chính là rủi ro cao: nên luôn có nguồn và kết quả kiểm chứng ở trước mắt; đừng giải thích dài cho câu thường.
- **Chỉ hiện độ chắc chắn khi nó đổi hành động của người dùng.** Một nhãn có ba mức với hành động rõ cho từng mức (đủ bằng chứng, một phần, không tìm thấy) tốt hơn một con số phần trăm dễ bị hiểu nhầm.
- **Nêu nguồn dữ liệu và chỗ thiếu.** Trích dẫn đã làm tốt; chỗ thiếu ("không có đoạn nào về …") cũng nên rõ như chỗ có.
- **Lỗi: nói cụ thể và chỉ đường tiếp.** Tránh câu lỗi chung và ngõ cụt. Mẫu của FinHelp từ 14/11 (xin lỗi, nói đúng giới hạn, gợi ý chia nhỏ, kèm đoạn trích) đúng hướng này; còn các câu từ chối cố định nên cũng gợi ý việc có thể làm.
- **Phản hồi rõ ràng, loại trừ nhau, nói tác động.** Nếu thêm nút đánh giá, giữ ít lựa chọn và nói nó dùng vào đâu (ở đồ án: để thu số liệu đánh giá, không phải để huấn luyện lại).

## 3. Việc nên làm, theo thứ tự (nhỏ, hợp MVP)

| # | Việc | Nguyên tắc | Công | Ghi chú |
|---|---|---|---|---|
| 1 | **Nhãn trạng thái trên mỗi câu trả lời** (đủ bằng chứng, một phần, không tìm thấy) và dòng cảnh báo gắn nhãn | G2, G10, PAIR hiệu chỉnh niềm tin | 1 ngày | Chính là GD-2 trong lộ trình (mức 2). Dữ liệu `answer_meta` đã có |
| 2 | **Một dòng giới hạn ở lần dùng đầu**: báo cáo tiếng Anh, hồ sơ SEC, không tư vấn đầu tư, số liệu được kiểm bằng mã | G1, G2 | 0,25 ngày | Chỉ chữ, không đổi backend |
| 3 | **Đánh giá và bình luận mỗi câu trả lời**, lưu cùng mã tin nhắn | G15, G16, PAIR phản hồi | 1 đến 1,5 ngày | Cần thêm trường ở backend (bạn duyệt). Có ích cho báo cáo (số liệu phản hồi tự nhiên); không bắt buộc cho MVP |
| 4 | **Nút hỏi lại câu này** | G9 | 0,5 ngày | Ưu tiên thấp |
| 5 | **Gợi ý cụ thể ở câu từ chối cố định** (ví dụ "hỏi theo từng công ty") | G10, PAIR ngõ cụt | 0,25 ngày | Chỉ đổi câu chữ; sửa `MSG` cần duyệt |

Không nên: cá nhân hóa (G13), thông báo thay đổi (G18) và tùy chọn toàn cục thêm (G17) trước bảo vệ: giá trị thấp so với công, và thêm chỗ sai khó đo.
