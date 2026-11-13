# FinHelp: Lộ trình đi tới bản MVP (Dev Roadmap V2)

> **Dự án tốt nghiệp:** Hệ thống Trợ lý AI Phân tích & Tra cứu Báo cáo Tài chính có Kiểm chứng Số liệu (**FinHelp**)
> **Sinh viên thực hiện:** Vũ Thành (MSSV: 20225405) - Trường CNTT & TT, ĐHBK Hà Nội (HUST)
> **Cập nhật:** 13/11/2026 (lần 3: viết lại toàn bộ theo từng việc, kèm lý do và mức ưu tiên). Trạng thái đã đối chiếu với code và git cùng ngày.
> **Mốc:** bảo vệ dự kiến 10/12/2026, còn 27 ngày.

Bản này thay cách trình bày cũ (mã F-1 đến F12, G1 đến G3, đợt A đến E, bảng ⏸ nằm rải ở nhiều mục) bằng **một danh sách việc duy nhất**. Mỗi việc có: làm gì, vì sao làm, mức ưu tiên, vì sao xếp mức đó, khi nào coi là xong, và sau MVP mở rộng thế nào. Mã cũ được ghi trong ngoặc để tra ngược.

Tài liệu liên quan:
- [ARCHITECTURE.md](../../ARCHITECTURE.md): kiến trúc đúng với code.
- [Version_3/PROJECT_PLAN.md](../Version_3/PROJECT_PLAN.md): kế hoạch tổng thể 09/11 và thiết kế vòng lặp "thiếu bằng chứng thì tìm lại".
- [Version_3/report_p0_suite_2026-11-13.md](../Version_3/report_p0_suite_2026-11-13.md): bảng điểm bộ test P0. [Version_3/plan_p0_tests.md](../Version_3/plan_p0_tests.md): nhật ký làm bộ test.
- `tối ưu.txt` (thư mục gốc): danh sách ca kiểm thử hành vi, nguồn của khái niệm "P0".

---

## 1. Cách đọc tài liệu này

**Thuật ngữ**

| Từ | Nghĩa |
|---|---|
| MVP | Bản sản phẩm nhỏ nhất dùng được và bảo vệ được. Định nghĩa cụ thể ở mục 2. |
| Ca P0 | 18 hành vi mà `tối ưu.txt` ghi là "phải đúng trước khi ra MVP" (ví dụ D07, G04, J03), cộng 5 ca thêm sau (C02b, E03w, G03, G16, T01). Tổng 23 ca trong `experiments/p0_suite/`. |
| Lỗi im lặng | Câu trả lời sai mà mọi bước kiểm tra đều cho qua, người dùng không có dấu hiệu nào để nghi ngờ. |
| Đoạn trích | Một đoạn của PDF được tìm ra và đưa cho mô hình ngôn ngữ đọc (trong code gọi là chunk). |
| Reranker | Mô hình chấm lại mức liên quan giữa câu truy vấn và từng đoạn trích (đang dùng Qwen3-Reranker-0.6B). |
| Bộ vàng | Bộ câu hỏi có đáp án và trang bằng chứng do người kiểm, dùng để đo. |

**Năm luồng việc.** Mọi việc thuộc đúng một luồng. Mã việc gồm tên luồng và số thứ tự; số không nói lên mức ưu tiên.

| Luồng | Mã | Câu hỏi nó trả lời |
|---|---|---|
| Tin cậy của câu trả lời | TC | Con số hệ thống đưa ra có đúng và có đủ không? |
| Vận hành | VH | Người khác có lấy mã nguồn về và chạy được không? |
| Đánh giá | DG | Số liệu trong báo cáo có chạy lại được từ kho mã không? |
| Giao diện | GD | Người dùng có nhìn thấy độ tin cậy đó không? |
| Đồ án | DA | Có đủ thứ để nộp và bảo vệ không? |

**Bốn mức ưu tiên**

| Mức | Tên | Nghĩa |
|---|---|---|
| 1 | Bắt buộc cho MVP | Thiếu thì không gọi là MVP. Không cắt. |
| 2 | Nên có | Làm sau khi mọi việc mức 1 của tuần đó xong. Cắt được nếu trễ. |
| 3 | Tùy chọn | Chỉ làm khi còn thừa thời gian. Cắt đầu tiên. |
| 4 | Sau MVP | Không làm trước bảo vệ. Ghi lại để biết hướng mở rộng (mục 8). |

**Quy tắc xếp mức.** Một việc lên mức 1 khi đúng ít nhất một điều sau, và càng đúng nhiều điều càng làm sớm:

1. **Nó chặn một lỗi im lặng.** Lỗi mà người dùng tự thấy được (báo lỗi, từ chối) ít nguy hiểm hơn lỗi đưa ra một con số sai trông như đúng. Sản phẩm này tồn tại vì lời hứa "số liệu có kiểm chứng".
2. **Thiếu nó thì không demo hoặc không bảo vệ được** (yêu cầu của phiếu giao nhiệm vụ, hệ thống sập giữa buổi demo, người chấm không chạy được).
3. **Việc khác phải chờ nó.**
4. **Nó rẻ và làm ngay được**: không cần GPU, không gọi mô hình trả tiền. Hiện hạn mức GPU Kaggle đã hết, nên việc làm được ngoại tuyến đi trước.

Việc lớn nhưng chỉ đúng điều 4 thì không lên mức 1.

**Ràng buộc làm việc (không đổi so với bản trước).** Mọi sửa trong `backend/` cần sinh viên duyệt trước. Mọi lần gọi mô hình trả tiền cần lời đồng ý kèm số lần gọi. Sửa prompt hệ thống thì gửi nguyên văn bản cũ và bản mới trước. Mỗi đợt dừng lại báo cáo rồi mới sang đợt sau. Chỉ đo câu hỏi tiếng Anh; tiếng Việt giữ cho chạy được nhưng không đo.

---

## 2. MVP là gì

Một câu: **một người chưa từng thấy dự án có thể mở FinHelp, tải lên báo cáo 10-K tiếng Anh, hỏi một câu về số liệu, nhận câu trả lời có trích dẫn tô sáng trên PDF; và với những kiểu lỗi đã biết, hệ thống hoặc trả lời đúng, hoặc nói rõ là nó thiếu bằng chứng.**

Bản MVP đạt khi cả 6 điều kiện sau đúng:

| # | Điều kiện | Hiện tại (13/11) | Việc đưa nó tới đạt |
|---|---|---|---|
| 1 | Luồng chính chạy trọn: đăng ký, tải PDF, hỏi, xem trích dẫn tô sáng, hỏi nối tiếp | Đạt từng phần riêng lẻ. Chưa chạy trọn một lượt trong ứng dụng thật sau khi gộp F9. | GD-1 |
| 2 | Không còn lỗi im lặng đã biết: con số gán nhầm năm, mục thiếu bằng chứng bị che | **Đạt một nửa.** T01 (gán nhầm năm) đạt 13/11; D07, G02 (mục thiếu bằng chứng bị che) còn trượt. | TC-1, TC-3 |
| 3 | Hạ tầng trục trặc thì người dùng nhận thông báo rõ, không phải lỗi chung | **Đạt với vector store** (J03 đạt 13/11). Chưa thử lỗi máy GPU và lỗi mô hình ngôn ngữ trong ứng dụng thật. | TC-2 |
| 4 | Người khác lấy mã nguồn về và chạy được theo hướng dẫn | **Chưa đạt.** Bản lấy về thiếu 5 file cần thiết, chưa có README. | VH-1 |
| 5 | Số liệu đo trong báo cáo chạy lại được bằng một lệnh từ kho mã | **Chưa đạt.** Mọi bộ đo nằm trong `experiments/` (git bỏ qua). | DG-1, DG-2 |
| 6 | Đủ "Nội dung 6" của phiếu giao nhiệm vụ | **Đã quyết 13/11: chỉ cần demo chạy được, không cần người dùng thật.** Phiếu ghi các gợi ý nối bằng "và/hoặc", và "thuật toán thử nghiệm với bộ dữ liệu thật" (FinanceBench) đã là một gợi ý hợp lệ. Còn lại: một kịch bản demo chạy trọn. | DA-1 |

Những thứ **không** thuộc MVP, dù hay: vòng lặp nhiều bước kiểu agent, LangGraph, kho tri thức khái niệm tài chính, đo tiếng Việt, so sánh 5 đến 10 công ty, hàng đợi Redis, thanh hạn mức token. Chúng nằm ở mục 8.

---

## 3. Đang đứng ở đâu (đối chiếu 13/11)

**Phần lõi đã xong và đã ở trên GitHub.** Tái cấu trúc backend thành 9 module; tìm kiếm lai (BGE-M3 dense và sparse, Qwen3-Reranker); bộ lập kế hoạch cho câu hỏi nhiều tài liệu và lưới an toàn; kiểm chứng con số và phép tính bằng code; lớp guard an toàn; hội thoại nối tiếp; trả lời dạng dòng chảy (SSE) có tiến trình; tô sáng trích dẫn trên PDF; trang quản trị; quên mật khẩu qua email; lưu file trên Cloudflare R2. Bảng trạng thái từng hạng mục cũ ở Phụ lục A.

**Sáu chỗ bản roadmap trước ghi sai hoặc chưa biết, nay đã kiểm:**

| # | Bản trước ghi | Thực tế kiểm 13/11 |
|---|---|---|
| 1 | Chưa đẩy `main` lên GitHub, bị từ chối 403 | **Đã đẩy xong.** `origin/main` và `origin/feat/f9-pdf-highlight` đều ở commit `4debdd1`, trùng với máy (`git ls-remote`). Mọi nhánh cục bộ đã gộp vào `main`. |
| 2 | "Chưa có README" (một dòng trong F11) | Nặng hơn thế: `.gitignore` đang chặn `docker-compose.yml` (luật `*.yml`), `backend/.env.example` (luật `.env.*`), 3 mẫu email trong `backend/app/templates/email/` (luật `templates/`), mọi file CI (luật `*.yml`), và luật mới chưa commit `/*.md` sẽ chặn luôn `README.md`. Người lấy mã về không có file nào trong số này. |
| 3 | Có `backend/Dockerfile`, `frontend/Dockerfile` | Có, nhưng chưa chạy được bằng một lệnh: backend dùng Python 3.10 (máy phát triển 3.13) và không cài thư viện mô hình; compose không truyền khóa bí mật và khóa API vào backend; frontend không có cấu hình nginx nên tải lại trang `/app` sẽ lỗi 404 và `/api` không tới backend. |
| 4 | Trạng thái bằng chứng "đã có `answer_meta`" | Backend có, **giao diện chat chưa hiển thị** (không tìm thấy trong `frontend/src/components/chat/`). |
| 5 | "Triển khai công khai" nằm trong mục "chưa làm trong lộ trình này" | Mẫu phiếu giao nhiệm vụ (Mẫu ĐATN 02) ghi Nội dung 6 "Triển khai trong thực tế và đánh giá, phản hồi của người sử dụng" là **bắt buộc với đồ án kỹ sư**. Sinh viên đã quyết ngày 13/11: chỉ cần demo (mục 7, quyết định 2). File `PGNV_Vũ Thành_20225405.xlsx` trong thư mục gốc vẫn là mẫu trống. |
| 6 | 740 test | Không chạy lại hôm nay. Đếm được 508 hàm `test_` trong 41 file; con số 740 là số ca sau khi nhân tham số ở lần chạy 13/11. |

**Chưa có trong code (đã tìm bằng grep):** trang chính sách riêng tư, xóa tài khoản, chặn gửi trùng một câu hỏi, cờ báo "kết quả bị suy giảm", kiểm cấu trúc đầu ra JSON của mô hình bằng Pydantic, nhãn loại câu hỏi, thử lại khi tìm kiếm hết giờ, thư mục `backend/evaluation/`, `.github/workflows/`, `frontend/nginx.conf`.

**Bảng điểm bộ test P0** (chi tiết trong báo cáo P0): 12 ca đạt rõ ràng. Các ca chưa đạt và việc xử lý:

| Ca | Hiện tượng | Việc |
|---|---|---|
| T01 | Con số đúng nhưng gán nhầm cột năm của bảng nhiều năm, cả hai bước kiểm tra đều cho qua | TC-1 |
| J03 | Tìm kiếm hết giờ: không thử lại, người dùng nhận `INTERNAL_ERROR` | TC-2 |
| D07, G02, G03 | Một mục thiếu bằng chứng bị các đoạn không liên quan che mất; không có lượt tìm bổ sung | TC-3 |
| E01 (đạt yếu), E03w | Bộ tính chỉ sửa số học, không biết công thức chuẩn của chỉ tiêu | TC-4 |
| G04 | Năm chỉ có ở cột so sánh: chỉ tìm trong một báo cáo, số liệu đã điều chỉnh không tới được mô hình | TC-5 |
| G16 | Nói "không công bố" khi thực ra chỉ là không tìm thấy | TC-6 |
| A04 | Câu "công ty nào tốt hơn" không qua cổng hỏi tiêu chí (mô hình tự xử lý ổn) | TC-7 |
| D03 | Chưa chạy: cần GPU | DG-2 |

---

## 4. Bảng điều khiển: mọi việc trong một bảng

Công sức tính bằng ngày làm việc tập trung. "Cần" ghi thứ phải có trước khi bắt đầu: **Duyệt** = sinh viên đồng ý sửa `backend/`; **GPU** = địa chỉ máy GPU từ xa còn sống; **API** = lời đồng ý gọi mô hình trả tiền kèm số lần; **Prompt** = duyệt nguyên văn dòng prompt.

| Mã | Việc (mã cũ) | Mức | Công sức | Cần | Trạng thái |
|---|---|---|---|---|---|
| **VH-1** | Kho mã lấy về là chạy được: sửa `.gitignore`, README, đưa file thiếu vào git (một phần F11) | 1 | 1,5 | | Đã làm 13/11, commit `03f2373` (kết quả ở mục 5) |
| **TC-2** | Thử lại khi tìm kiếm hết giờ, mã lỗi riêng (B1) | 1 | 0,5 | Duyệt | Đã làm 13/11, commit `6026fde` (kết quả ở mục 5) |
| **TC-1** | Kiểm cột năm của bảng (B5) | 1 | 2,5 | Duyệt | Đã làm và commit 13/11 (kết quả ở mục 5) |
| **DG-1** | Bộ đánh giá vào kho mã, chạy lại bằng một lệnh (F2) | 1 | 2,5 | Sinh viên chấm xong 200 câu nhiều tài liệu (cuối tuần sau, khoảng 22–23/11) | Chưa làm |
| **TC-3** | Kiểm đủ bằng chứng theo từng mục, tìm bổ sung 1 lần (B2) | 1 | 2 + 1 đo | Duyệt; đo cần GPU, API | Chưa làm |
| **TC-4** | Bảng chỉ tiêu chuẩn, bản tối thiểu (C1) | 1 | 3 | Duyệt | Chưa làm |
| **DG-2** | Một đợt đo có GPU và API: bảng trước/sau, ngưỡng cho TC-3, ca D03 | 1 | 1 | GPU, API | Chờ GPU |
| **GD-1** | Chạy trọn luồng chính trong ứng dụng thật, gồm cả tô sáng (đợt A cũ) | 1 | 0,5 | Backend chạy | Một lượt đầu đã chạy 13/11 trên đường local; còn hỏi nối tiếp và so sánh hai công ty |
| **DA-1** | Nội dung 6: kịch bản demo chạy trọn (không cần người dùng thật) | 1 | 0,5 | GD-1, DG-2 | Đã quyết 13/11 |
| **DA-2** | Báo cáo, slide, video demo (F12) | 1 | chạy song song | | Chưa làm |
| TC-5 | Năm chỉ có ở cột so sánh: tìm mọi báo cáo hoặc báo có bản điều chỉnh (B3) | 2 | 1 | Duyệt | Chưa làm |
| VH-2 | Kiểm tra tự động khi đẩy mã (CI) (một phần F11) | 2 | 0,5 | VH-1 | Chưa làm |
| DG-3 | Đưa ca P0 vào `backend/tests/` làm test hồi quy | 2 | 1 | Duyệt; quyết định 5 | Sinh viên: chưa làm vội |
| GD-2 | Hiện trạng thái bằng chứng trên giao diện (đợt D cũ) | 2 | 1 | | Chưa làm |
| DA-3 | Vẽ lại sơ đồ thiết kế cho đúng code | 2 | 1 | | Chưa làm |
| VH-3 | Chạy bằng một lệnh Docker | 2 | 2 | VH-1 | Chưa làm |
| DG-4 | So sánh 10 câu với NotebookLM; báo cáo thử tấn công | 2 | 1,5 | API (ít) | Chưa làm |
| TC-6 | Một dòng prompt: "không tìm thấy" khác "không công bố" (B4) | 3 | 0,5 | Prompt, API | Chờ |
| TC-7 | Cổng hỏi tiêu chí cho câu "công ty nào tốt hơn" | 3 | 0,5 | Duyệt | Chưa làm |
| VH-4 | Trang riêng tư, xóa tài khoản | 3 (chỉ lên 1 nếu sau này mở ra mạng) | 1 | Duyệt | Chưa làm |
| VH-5 | Chặn gửi trùng, kiểm cấu trúc JSON của mô hình, cờ suy giảm | 3 | 2 | Duyệt | Chưa làm |
| GD-3 | Gợi ý câu hỏi tiếp theo sinh theo chỉ tiêu | 3 | 1 | Duyệt | Chưa làm |
| GD-4 | Báo cáo phân tích một công ty, xuất Excel | 3 | 3 | TC-4 | Chưa làm |

Tổng mức 1 không kể báo cáo: khoảng **16 ngày công** trong 27 ngày lịch. Vừa đủ nếu báo cáo (DA-2) được viết song song từ tuần đầu, và **không còn chỗ cho việc mức 2 nếu một việc mức 1 trượt hạn**. Xem thứ tự cắt ở mục 6.

---

## 5. Chi tiết từng việc mức 1 và mức 2

### Luồng TC: tin cậy của câu trả lời

Đây là luồng làm nên khác biệt với NotebookLM. Kết luận chính của bộ test P0: mô hình ngôn ngữ đã trung thực khi nhận đoạn trích gọn; chỗ thiếu nằm ở **cái gì tới được mô hình** và **cái gì được kiểm sau khi mô hình trả lời**.

#### TC-1. Kiểm cột năm của bảng (mã cũ B5) · Mức 1

- **Làm gì.** Với mỗi con số trong câu trả lời có gắn năm: tìm ô chứa con số đó trong bảng Markdown của đoạn trích, đọc năm ở hàng tiêu đề của cột, so với năm mà câu trả lời gán. Lệch thì thêm một lỗi vào danh sách lỗi của bước kiểm chứng, để được sửa một lần hoặc đánh dấu như các lỗi khác. Con số có ở nhiều cột thì chấp nhận nếu một cột khớp năm. Nơi sửa: module mới trong `generation/answer_check/`, nối vào `verification.py`. Cách tách từ và số có thể mượn từ `locateExcerpt.ts` của F9.
- **Vì sao làm.** Báo cáo 10-K in ba năm cạnh nhau. Bước kiểm số hiện chỉ hỏi "con số có trong một đoạn trích nào không"; bước kiểm trích dẫn so năm theo cả báo cáo, nên báo cáo năm 2019 (phủ 2017 đến 2019) không bao giờ bị coi là sai kỳ. Đã kiểm bằng tay: câu gán 52,4 cho năm 2019 trong khi nó thuộc cột 2017 qua được cả hai bước.
- **Vì sao mức 1.** Đúng điều 1 và 4: đây là lỗi im lặng nặng nhất còn lại, nó đánh thẳng vào lời hứa "có kiểm chứng", nhắc trong prompt không chặn được, và sửa hoàn toàn bằng code, không cần GPU hay tiền.
- **Xong khi.** Ca T01 đạt; chạy bộ kiểm trên các câu trả lời thật đã lưu và ghi lại tỷ lệ báo nhầm; nếu tỷ lệ báo nhầm cao thì để sau một cờ cấu hình tắt mặc định và ghi con số vào báo cáo. Toàn bộ test cũ vẫn qua.
- **Kết quả làm ngày 13/11 (đã commit).** Module mới `generation/answer_check/column_years.py` (`check_columns`), nối vào `verification.verify`: vấn đề thêm vào danh sách sửa một lần như các lỗi khác, ghi vào dấu vết (`number_check.columns`, `verification.columns`), và nếu vẫn còn thì ghi chú dưới câu trả lời. Cờ `COLUMN_CHECK_ENABLED` (mặc định **bật**, vì đo xong chỉ còn báo đúng).
  - **Cách đọc.** Với mỗi con số một câu (hoặc một ô bảng trong câu trả lời) nêu cho một năm và trích tới [n]: năm là năm câu gắn với con số ("... 16,7 % in FY2019" hoặc năm duy nhất của câu không so sánh gì); số được tìm trong các ô bảng Markdown của đoạn trích [n]; năm của cột đọc từ hàng tiêu đề (tiêu đề có thể nằm dưới một hàng tiêu đề lớn; tiêu đề dạng ngày "January 28, 2023" cũng nhận năm tài chính trước đó). Chỉ báo khi số **chỉ** nằm trong bảng, **chỉ** ở các cột đã biết năm, và không cột nào là năm câu nêu. Bỏ qua: số không có trong bảng nào, số cũng có trong phần văn xuôi, bảng lệch cột với tiêu đề, cột không có một năm duy nhất, chuỗi số kèm chuỗi năm ("for 2019/2018/2017"), số theo tỷ ("$1,2 billion"), số thập phân nhỏ, ngày trong tháng.
  - **Kết quả đo.** T01 đạt (L0: 9 đạt, 2 trượt là A04 và E03w). 769 test qua (thêm 20 ca mới ở `test_column_years.py`). Đo miễn phí trên **290 câu trả lời đã lưu** có đoạn trích đầy đủ (`experiments/scripts/rag_improvement/tc1_columns.py`): 575 con số có năm và trích dẫn, **457 kiểm được**; bản đầu báo 7 con số, đọc từng câu thấy 6 là báo nhầm (danh sách số kèm danh sách năm, ngày "January 28" bị đọc là số 28, câu có hai năm trong ngày, số theo tỷ, số thập phân nhỏ), đã sửa từng nguyên nhân và thêm ca test từ chính các câu đó; sau sửa còn **1 báo cáo và đó là lỗi thật**: câu trả lời gán 666 triệu USD cho FY2015 của eBay trong khi đoạn trích là báo cáo FY2019, nơi 666 nằm ở cột 2017. Chú ý: bốn sửa được chỉnh trên đúng tập 290 câu này nên "0 báo nhầm" là con số lạc quan, cần thêm câu trả lời mới để xác nhận. Thử cài lỗi: chuyển năm của mỗi con số sang một năm khác của bảng thì bắt được 330 trên 420 (78,6 %); phần còn lại là số in ở nhiều cột hoặc rơi vào quy tắc nhận năm sau của tiêu đề ngày.
  - **Nguyên nhân của báo cáo thật (eBay, `mdg_b02_006`, tình huống k5), đã mở chunk đối chiếu với PDF gốc:** parsing **đúng** (trang 68: chi đầu tư `(554) (651) (666)` dưới 2019/2018/2017; trang 35: doanh thu 5 cột, 8.592 là 2015). Lỗi do **mô hình**: ngữ cảnh không có báo cáo eBay FY2015 nên không có chi đầu tư 2015, mô hình lấy 666 (cột 2017, ngoài cùng bên phải) làm FY2015. Đó là bản trả lời không qua lưới an toàn; cùng câu hỏi, lần chạy có lưới trả lời đúng (eBay 668 / 8.592 = 7,8 %, Intel 13,2 %) và có lần trả lời đầu tự nhận thiếu. Lưới cứu một phần: đủ bằng chứng k3 75,7 %, k4 78,6 %, k5 64,3 % (từ 0 %); phần còn thiếu thuộc TC-3.
  - **Chưa làm.** Kiểm nhãn dòng (đúng chỉ tiêu, không chỉ đúng năm) và đơn vị cột; chưa thử trên câu trả lời tiếng Việt; chưa thử trong ứng dụng thật với một câu mới (cần lời gọi mô hình).
  - **Đồng bộ tiếng Việt và sửa báo nhầm (13/11, viết test trước, chưa commit, 780 test qua).** Nguyên nhân tìm thấy trên một câu trả lời tiếng Việt đã lưu (câu ROIC, tốn thêm một lần viết lại và 37 giây): bộ đọc phép tính viết ra (`calculations.py`) chỉ hiểu số kiểu Anh, nên "12 421 × 0,8937 = 11 100,6" bị coi là số không kiểm chứng được; bản cũ còn sửa sai một kết quả đúng ở kiểu "1.197 / 11.261 = 10,63%" (thành "11%"). Nay đọc được ba kiểu ("11,100.6", "11 100,6", "11.100,6") qua `amounts._interpret`; kết quả chỉ được sửa khi mọi cách đọc cho cùng một kết quả. Kiểm cột năm (`column_years.py`) có thêm từ nối, từ so sánh, ngày tháng và "tỷ" tiếng Việt, và bỏ qua số dư đầu kỳ ở cả hai ngôn ngữ ("Beginning inventory", "đầu kỳ": số đầu kỳ của FY2018 là số cuối năm 2017, trước đó bị báo nhầm 6 lần trên một câu đã lưu). Đo lại miễn phí: bản cũ và bản mới cho kết quả giống hệt trên 290 câu trả lời tiếng Anh đã lưu (422 phép tính, 7 lần sửa); TC-1 vẫn còn đúng 1 báo cáo (lỗi thật của eBay), bắt lỗi cài 78,0 %. Chưa làm: số nhóm bằng dấu chấm ("12.421") trong kiểm cột năm.
- **Giới hạn biết trước.** Tiêu đề bảng nhiều tầng, đơn vị khác nhau giữa các cột, bảng bị bóc tách sai thì không kiểm được. Ở bài đo 12/11, chỉ 33,6 % con số đã kiểm nằm trên một dòng bảng có nhãn; phần còn lại nằm trong câu văn.
- **Mở rộng sau MVP.** Kiểm thêm nhãn dòng (đúng chỉ tiêu, không chỉ đúng năm) và đơn vị của cột; xa hơn là đọc số liệu có cấu trúc XBRL của SEC để mỗi con số mang sẵn chỉ tiêu, kỳ và đơn vị (mục 8, hướng 3).

#### TC-2. Thử lại khi tìm kiếm hết giờ, mã lỗi riêng (mã cũ B1) · Mức 1

- **Làm gì.** Bọc các lời gọi tìm kiếm trong `retrieval_step.py` bằng một lần thử lại có giới hạn; khi vẫn hỏng, trả mã lỗi riêng (ví dụ `SEARCH_UNAVAILABLE`) thay cho `INTERNAL_ERROR`. Câu hiển thị cho người dùng vẫn là câu chung "hệ thống đang bận, vui lòng thử lại", không nêu tên thành phần.
- **Vì sao làm.** Hiện tìm kiếm chờ Qdrant 60 giây, máy GPU 180 giây, rồi bỏ; lỗi hết giờ thành lỗi 500 chung. Đường hầm tới máy GPU từ xa đã chết sau khoảng một giờ trong các lần thử ngày 12/11.
- **Vì sao mức 1.** Đúng điều 2 và 4: buổi demo chạy trên chính hạ tầng hay rớt này, và việc này nhỏ nhất trong danh sách (nửa ngày). Làm đầu tiên trong luồng TC để các đợt đo sau đỡ hỏng giữa chừng.
- **Xong khi.** Ca J03 đạt trên `run_l1.py`; có test cho cả hai nhánh (thử lại thành công, thử lại vẫn hỏng).
- **Kết quả làm ngày 13/11 (commit `6026fde`).** Hàm `search_with_retry` trong `chat/retrieval_step.py` bọc mọi lời gọi tìm; thử lại `SEARCH_RETRIES` lần (mặc định 1, nghỉ 1 giây) với lỗi hết giờ, mất kết nối, lỗi truyền của httpx và lỗi Qdrant; vẫn hỏng thì trả `ServiceUnavailableError` mã mới `search_unavailable` (503), có câu tiếng Anh và tiếng Việt trong giao diện. Lỗi lập trình (ví dụ `KeyError`) và lỗi máy GPU (đã tự gửi lại một lần ở `gpu_client`) không bị thử lại. Một thay đổi hành vi nhỏ: bước tìm thêm **sau** câu trả lời (`_search_more`) nếu hỏng thì giữ câu trả lời đã viết, ghi `search_failed` vào dấu vết, thay vì biến cả câu hỏi thành lỗi. `run_l1.py`: **J03 đạt** (2 lần thử, lỗi có mã); L1 từ 5 đạt, 4 trượt thành 6 đạt, 3 trượt (D07, G02, G04), 1 không áp dụng (G03). `pytest`: 749 qua (740 cũ, 8 ca mới ở `test_search_retry.py`, 1 ca mới ở `test_lazy_net.py`); `tsc` sạch.
- **Mở rộng sau MVP.** Chỉ chạy lại nhánh lỗi thay vì cả câu hỏi; ngắt mạch khi máy GPU hỏng liên tục; khi phải bỏ qua bước reranker thì gắn cờ "suy giảm" cho người dùng biết (VH-5).

#### TC-3. Kiểm đủ bằng chứng theo từng mục, tìm bổ sung một lần (mã cũ B2) · Mức 1

- **Làm gì.** Bộ lập kế hoạch đã cho danh sách các cặp (tài liệu, mục cần tìm). Sau khi tìm, chấm từng cặp: cặp nào không có đoạn trích nào đạt ngưỡng điểm reranker thì coi là thiếu; tìm bổ sung đúng cặp đó tối đa 1 lần; vẫn thiếu thì báo cho mô hình "mục này chưa có bằng chứng" để nó nói thật thay vì đoán. Nơi sửa: `retrieval_step.py`, `hybrid_search.py` (đưa điểm reranker ra ngoài).
- **Vì sao làm.** Tìm kiếm vector luôn trả về cái gì đó, nên ghi chú "không tìm thấy đoạn nào" hiện gần như không bao giờ bật. Hệ thống biết một tài liệu rỗng, chưa biết một mục thiếu. Khi so sánh 5 công ty mà một công ty thiếu doanh thu, câu trả lời có thể lặng lẽ bỏ công ty đó.
- **Vì sao mức 1.** Đúng điều 1 và 3: đây là lỗi im lặng về độ đầy đủ, và là "vòng lặp tìm lại" mà mọi hướng mở rộng kiểu agent ở mục 8 phải dựng lên trên. Nó cũng là phần mới có giá trị nhất để viết trong báo cáo.
- **Điểm cần lưu ý.** Ngưỡng điểm không chọn bằng tay. Phần code làm ngay được, để sau một cờ cấu hình **tắt mặc định**. Việc đo ngưỡng trên bộ vàng nhiều tài liệu và quyết định bật nằm trong DG-2 (cần GPU và API). Nếu đo cho thấy không tốt hơn thì giữ cờ tắt và đưa kết quả vào báo cáo: đó vẫn là một kết quả có giá trị.
- **Đo thiết kế trước khi viết code (13/11, miễn phí, điểm Qwen đã lưu, `experiments/scripts/rag_improvement/d2_year.py`).** 192 câu nhiều tài liệu (164 đủ bằng chứng, 28 thiếu), 706 cặp (mục, tài liệu); chấm trên đúng các đoạn trích được chọn. Quy tắc "cặp có ít nhất một đoạn đạt ngưỡng điểm reranker": AUC 0,56; ở ngưỡng 0,15 bắt **0/28** câu thiếu (báo nhầm 1/164). Thêm điều kiện "đoạn đó có năm câu hỏi hỏi": AUC 0,62; ở 0,15 bắt **2/28** (báo nhầm 6/164). **Vì sao:** 28 câu thiếu có 40 mục bằng chứng bị thiếu; chỉ 2 mục thuộc tài liệu mà kế hoạch không tìm, còn **38 mục thuộc tài liệu đã có đoạn trích được chọn, chỉ là sai trang** (đúng chủ đề, không đúng con số). Điểm reranker chấm "đúng chủ đề" nên không thấy loại thiếu này; quy tắc chỉ bắt được kiểu D07 (tài liệu không có đoạn nào về mục). Bài đo cũ D2 (12/11) cũng cho thấy câu cường độ chi đầu tư dù đúng file chỉ được chấm 0,07 đến 0,25, nên ghi chú cho mô hình phải ở dạng mềm.
- **Hướng 2 được chọn 13/11: tìm lại khi câu trả lời tự nhận thiếu, bỏ các đoạn đã có (`d2_retry.py`, miễn phí).** Khi câu trả lời ghi `partial` hoặc `not_found`, tìm lại mọi cặp (mục, tài liệu) của kế hoạch, bỏ các đoạn đã chọn, thêm N đoạn kế tiếp của mỗi cặp vào **cuối** ngữ cảnh. Trên 28 câu thiếu (40 mục): tối đa 25 mục còn nằm trong danh sách của cặp; N = 1 lấy lại 10 mục (8 câu thành đủ, thêm trung vị 4 đoạn, 2.842 token); **N = 2 lấy lại 13 mục (11 câu thành đủ, thêm trung vị 6 đoạn, 4.978 token, tối đa 12.626)**; N = 3 lấy lại 15 (12 câu, thêm 7.349 token); có ngưỡng 0,15 thì N = 2 còn 9 mục (8 câu, thêm 3.000 token). Điều kiện kích hoạt (`lazy_net_status.json`, 40 câu trả lời thật): ngữ cảnh thiếu thì câu trả lời tự nhận `partial`/`not_found` 20/29 lần, ngữ cảnh đủ thì 0/11 lần. **Kích thước ngữ cảnh (lost in the middle):** lượt đầu gửi trung vị 9 đoạn trên 423 đoạn của các tài liệu được tìm (1,98 %, tối đa 16 đoạn, trung vị 6.400 token, tối đa 12.119); bằng chứng tìm được nằm ở một phần ba đầu 415/603 lần, giữa 140, cuối 48, vì ngữ cảnh xếp theo độ liên quan. Đoạn tìm lại được nối vào cuối nên không rơi vào giữa.
- **Kiểm "không phải brute force" (`d2_budget.py`, miễn phí).** Cùng 192 câu, token cộng trên mọi câu, tỷ lệ kích hoạt lấy từ `lazy_net_status.json`. Tìm lại có điều kiện N = 2: kỳ vọng lấy lại 9,0/40 mục với 102.063 token (532 token mỗi câu); thêm đều cho mọi câu thì cần +4 đoạn mỗi câu (516.891 token, gấp 5 lần) mới được 9/40. Hiệu quả 8,8 mục trên 100.000 token so với 1,4 đến 2,8 của cách thêm đều; N = 1 hiệu quả nhất (12,1). Độ chính xác ngữ cảnh (tỷ lệ đoạn gửi đi có chứa bằng chứng): 27,0 % trên mọi câu ở lượt đầu; ở câu thiếu 15,8 % → 12,1 % sau N = 2, tức có thêm đoạn nhiễu. Thước đo cuối cùng là độ đúng câu trả lời (để sau, cần API).
- **Quyết định 13/11 về G02 (phương án A).** TC-3 chỉ kiểm những mục kế hoạch có ghi. Khi bộ lập kế hoạch **bỏ sót** một mục (kịch bản G02 hiện tại: kế hoạch chỉ có "Walmart revenue", không có "Walmart net income"), không cặp nào thiếu nên TC-3 không thấy gì; ca này giữ trạng thái trượt và được ghi là giới hạn của bộ lập kế hoạch. Trường hợp kế hoạch có mục nhưng lần tìm đầu bỏ lỡ thì thuộc TC-3 (test `test_g02_...` trong `backend/tests/test_evidence_check.py`).
- **Xong khi.** D07, G02, G03 đạt trên bộ giả của `run_l1.py`; câu hỏi đủ bằng chứng ngay lượt đầu không tốn thêm lượt tìm nào (ca K01 vẫn đạt); có test chứng minh dừng sau đúng 1 lần tìm bổ sung.
- **Mở rộng sau MVP.** Viết lại truy vấn cho mục thiếu bằng một lời gọi mô hình thay vì tìm lại bằng truy vấn cũ; nâng lên 2 lần tìm lại; câu hỏi nhiều bước (mục 8, hướng 1).

#### TC-4. Bảng chỉ tiêu chuẩn, bản tối thiểu (mã cũ C1) · Mức 1

- **Làm gì.** Một bảng dữ liệu trong code: tên chỉ tiêu, công thức, đầu vào, tên gọi khác, lưu ý (ví dụ ROA dùng tổng tài sản bình quân). Soạn từ giáo trình CFA có sẵn trên máy. Bộ tính hiện có (`answer_check/calculations.py`) dùng bảng này để kiểm cả công thức, không chỉ số học. Bản tối thiểu: khoảng 15 đến 20 chỉ tiêu hay gặp nhất (biên lợi nhuận gộp, biên hoạt động, biên ròng, ROA, ROE, tăng trưởng, dòng tiền tự do, thuế suất hiệu dụng, tỷ số thanh toán hiện hành và nhanh, vòng quay hàng tồn kho, số ngày phải thu, nợ trên vốn chủ, cường độ đầu tư tài sản cố định).
- **Vì sao làm.** Khi mô hình được suy nghĩ, lỗi số học gần như bằng 0 (0 trên 167 phép tính viết ra trong bài đo 12/11). Loại lỗi còn lại nhiều nhất trên FinanceBench là **sai công thức, sai định nghĩa hoặc sai dòng đầu vào** (14 câu sai dù đã có đúng trang). Bộ tính hiện tại không bắt được loại này: ca E03w trượt, ca E01 đạt yếu.
- **Vì sao mức 1.** Đúng điều 1 và 4: nó nhắm đúng loại lỗi lớn nhất đã đo được, và làm ngoại tuyến hoàn toàn. Nó cũng là phần "phân tích tài chính" phân biệt sản phẩm với một công cụ hỏi đáp PDF chung. Việc này không phụ thuộc quyết định về kho tri thức (quyết định 4).
- **Vì sao chỉ bản tối thiểu.** Bản đầy đủ là việc lớn; 15 đến 20 chỉ tiêu phủ phần lớn câu hỏi tính toán của FinanceBench và đủ để chứng minh cơ chế.
- **Xong khi.** Viết ca P0 mới cho bảng chỉ tiêu **trước** khi viết code; E01 và E03w đạt; không báo nhầm trên các câu trả lời đúng đã lưu.
- **Mở rộng sau MVP.** Thêm chỉ tiêu; báo cáo phân tích một công ty (GD-4); quét "dấu hiệu cần chú ý" theo CFA; kho đoạn trích giáo trình để trả lời câu hỏi khái niệm (mục 8, hướng 2).

#### TC-5. Năm chỉ có ở cột so sánh của nhiều báo cáo (mã cũ B3) · Mức 2

- **Làm gì.** Khi năm được hỏi chỉ xuất hiện ở cột so sánh của nhiều báo cáo, tìm trong tất cả các báo cáo đó, hoặc tối thiểu báo cho người dùng biết có bản số liệu đã điều chỉnh. Nơi sửa: `target_scope.py`.
- **Vì sao làm.** Quy tắc hiện tại "lấy từ báo cáo sớm nhất có năm đó" che mất số liệu đã điều chỉnh (ca G04): người dùng thấy số cũ mà không biết có số mới.
- **Vì sao mức 2, không phải 1.** Chỉ ảnh hưởng nhóm câu hỏi về năm không có báo cáo riêng và có điều chỉnh số liệu; phạm vi hẹp hơn TC-1 và TC-3. Nhưng nó nhỏ (1 ngày) và là ca P0, nên là **việc mức 2 làm đầu tiên**.
- **Xong khi.** Ca G04 đạt trên `run_l1.py`; chi phí tăng thêm ở các câu hỏi này được ghi lại.
- **Mở rộng sau MVP.** Phân biệt ba loại số: báo cáo gốc, đã điều chỉnh, và số không theo chuẩn kế toán (GAAP và non-GAAP).

### Luồng VH: vận hành

#### VH-1. Kho mã lấy về là chạy được · Mức 1

- **Làm gì.**
  1. Sửa `.gitignore`: bỏ luật `*.yml`; thêm ngoại lệ `!.env.example`, `!README.md`; đổi `templates/` và `storage/` thành đường dẫn cụ thể để không chặn `backend/app/templates/email/`. Giữ nguyên việc bỏ qua `docs/Version_3/` và `experiments/` (quyết định ngày 13/11).
  2. Đưa vào git: `docker-compose.yml`, `backend/.env.example`, 3 mẫu email.
  3. Bỏ `frontend/tsconfig.tsbuildinfo` khỏi git (file build bị commit nhầm).
  4. Viết `README.md`: dự án là gì, kiến trúc một đoạn, cách chạy từng bước (MongoDB và Qdrant bằng Docker, backend bằng môi trường ảo Python, frontend bằng `npm`), biến môi trường, giới hạn đã biết.
  5. Kiểm việc chuyển đổi cấu trúc MongoDB V3 đã chạy trên cơ sở dữ liệu thật chưa bằng `scripts/inspect_db.py` (chỉ đọc). Đây là dòng "chưa xác minh" của hạng mục F3.5 cũ.
  6. Kiểm bằng cách lấy mã về một thư mục tạm và làm theo README.
- **Vì sao làm.** Xem dòng 2 bảng "sáu chỗ ghi sai" ở mục 3: hiện một bản lấy về không có compose, không có mẫu biến môi trường, không có mẫu email, không có hướng dẫn.
- **Vì sao mức 1.** Đúng điều 2, 3 và 4: giảng viên hay hội đồng không thể chạy thử; VH-2, VH-3 và DA-1 đều phải chờ nó; và nó không cần GPU, không cần duyệt sửa `backend/` (chỉ thêm file vào git). Vì thế nó là **việc làm đầu tiên của cả lộ trình**.
- **Xong khi.** Từ bản lấy về sạch, làm theo README: đăng nhập, tải PDF, hỏi, nhận câu trả lời có trích dẫn.
- **Kết quả làm ngày 13/11 (commit `03f2373`).**
  - `.gitignore`: bỏ `*.yml`; thêm `!.env.example` và `!README.md`; `templates/` thành `/templates/`; `storage/` thành `/storage/` và `/backend/storage/` (luật cũ còn che cả `backend/app/infrastructure/storage/__init__.py`); `.docx` thành `*.docx`; thêm `*.tsbuildinfo`. `frontend/tsconfig.tsbuildinfo` đã gỡ khỏi chỉ mục git (file vẫn ở trên máy).
  - Git nay thấy thêm: `docker-compose.yml`, `backend/.env.example`, 3 mẫu email, `backend/app/infrastructure/storage/__init__.py`, `README.md`. Vẫn bị bỏ qua: `.env`, `.env.dev`, `backend/storage/`, `docs/Version_3/`, `experiments/`, `ARCHITECTURE.md`, `frontend/dist`, `node_modules`. Đã kiểm trên một bản sao chỉ gồm các file git thấy.
  - `backend/.env.example`: cổng MongoDB đổi từ 27017 sang 27018 cho khớp `docker-compose.yml` (trước đây người làm đúng README sẽ không kết nối được); thêm dòng ghi chú cho `REMOTE_GPU_URL` và `FRONTEND_URL`.
  - **Lỗi tìm thấy khi thử trên bản sao sạch:** chép nguyên `.env.example` thành `.env` thì 33 file test không thu thập được và server không khởi động, vì dòng `ADMIN_PASSWORD=` để trống không qua kiểm tra tối thiểu 8 ký tự. Đã đổi thành dòng chú thích. Sau sửa, bản sao chỉ gồm file git thấy chạy `pytest` qua 740 ca và `app.main` nạp được.
  - **Chưa kiểm:** `npm install` và `npm run build` trên bản sao sạch, và toàn bộ luồng đăng nhập, tải PDF, hỏi (cần Docker, hiện chưa chạy trên máy này). Việc đó thuộc GD-1.
  - **Cơ sở dữ liệu MongoDB V3 (hạng mục F3.5) đã xác minh bằng truy vấn chỉ đọc:** trên `datn_finance` (Atlas), 4 người dùng và 3 sổ tay đều ở dạng mới, không còn bản ghi dạng cũ, không còn collection `chat_sessions`. Hai chỉ mục cũ `email_1` và `username_1` của `users` vẫn còn; chưa rõ có trùng tên với chỉ mục V3 hay không nên chưa xóa. Lưu ý: `migrate_mongo_v3.py --dry-run` báo "STOP" trên cơ sở dữ liệu này vì nó chỉ đếm số bản ghi trong 4 collection, không phân biệt dạng cũ hay mới; đừng đọc "STOP" đó là chưa chuyển đổi.
- **Mở rộng sau MVP.** VH-3 (một lệnh Docker), rồi triển khai công khai ổn định (mục 8, hướng 6).

#### VH-2. Kiểm tra tự động khi đẩy mã (CI) · Mức 2

- **Làm gì.** Một file `.github/workflows/ci.yml` chạy `pytest`, `tsc`, `vite build`, `npm run test:highlight`.
- **Vì sao làm.** Hơn 700 ca test đang chỉ chạy khi nhớ chạy tay. Ba tuần tới sẽ sửa `backend/` nhiều lần liên tiếp.
- **Vì sao mức 2.** Rẻ (nửa ngày) và bảo vệ các sửa của luồng TC, nhưng thiếu nó sản phẩm vẫn chạy và vẫn bảo vệ được. Phải chờ VH-1 vì luật `*.yml` đang chặn file CI.
- **Xong khi.** Một lần đẩy mã làm CI chạy và báo xanh.
- **Mở rộng sau MVP.** Thêm kiểm kiểu viết code (`ruff`), đo độ phủ test, đặt ngưỡng chặn.

#### VH-3. Chạy bằng một lệnh Docker · Mức 2

- **Làm gì.** Sửa `backend/Dockerfile` (Python 3.13, người dùng không phải root, kiểm tra sức khỏe), thêm `frontend/nginx.conf` (mở thẳng `/app`, chuyển `/api` sang backend, tắt đệm cho SSE), compose đọc `env_file`.
- **Vì sao mức 2.** MVP chỉ cần "chạy được theo hướng dẫn" (VH-1). Một lệnh Docker tiện hơn nhưng tốn 2 ngày, và ảnh backend có mô hình rất nặng. Vẫn mức 2 vì sinh viên đã chọn chỉ demo (quyết định 2); lên mức 1 nếu sau này mở ra mạng bằng Docker.

### Luồng DG: đánh giá

#### DG-1. Bộ đánh giá vào kho mã (mã cũ F2) · Mức 1

- **Làm gì.** Tạo `backend/evaluation/`: sao chép các script đo cần thiết từ `experiments/` (không đưa dữ liệu nặng vào git); hai bộ câu hỏi: **FinanceBench 150 câu** (một tài liệu, để so với số đã có) và **bộ nhiều tài liệu 200 câu do sinh viên tự tạo và tự chấm**; thêm bộ guard đã có (câu ngoài phạm vi, tấn công prompt) nếu còn chỗ; một file đặc tả cách đo; một lệnh chạy lại. Quyết định ngày 13/11 thay cho bộ 30 câu nhỏ tôi đề xuất lúc đầu.
- **Vì sao làm.** Mọi con số sẽ trích trong báo cáo (FinanceBench 27/30, độ đủ bằng chứng 89 %, guard 32/32...) đều nằm trong thư mục git bỏ qua. Người đọc báo cáo không thể chạy lại.
- **Vì sao mức 1.** Đúng điều 2 và 3: một đồ án về "số liệu có kiểm chứng" mà số liệu của chính nó không kiểm chứng được là điểm yếu dễ bị hỏi nhất; và mọi việc luồng TC cần bộ đo này để có bảng trước/sau.
- **Cần sinh viên.** Đáp án của 200 câu nhiều tài liệu do sinh viên chấm, dự kiến xong cuối tuần sau (khoảng 22–23/11). Việc dựng khung `backend/evaluation/` (chép script, đặc tả đo, lệnh chạy) làm trước được với FinanceBench 150 câu; phần nhiều tài liệu chờ đáp án. Nếu chấm trễ, đo trên phần đã chấm xong thay vì chờ đủ 200.
- **Xong khi.** Một lệnh in ra bảng chỉ số (độ đúng số liệu, tỷ lệ trích dẫn đúng, tỷ lệ từ chối đúng, thời gian, chi phí mỗi câu); phần không cần mô hình thật chạy được không tốn tiền.
- **Mở rộng sau MVP.** Chạy 2 lần mỗi cấu hình để đo độ ổn định; bộ tiếng Việt; chạy tự động hằng tuần.

#### DG-2. Một đợt đo có GPU và API · Mức 1, đang chờ GPU

- **Làm gì.** Gom mọi việc cần máy GPU hoặc mô hình trả tiền vào **một đợt**, chuẩn bị sẵn script để chạy liền một mạch:
  1. Bảng mốc "trước": bộ vàng trên code hiện tại.
  2. Đo ngưỡng điểm reranker cho TC-3, rồi quyết bật hay tắt mặc định.
  3. Ca D03: tìm trên PDF thật với ba báo cáo.
  4. Bảng "sau": cùng bộ vàng, sau TC-1 đến TC-4.
  5. Nếu làm TC-6: đo dòng prompt đó.
- **Vì sao gom một đợt.** Đường hầm tới máy GPU sống khoảng một giờ và địa chỉ đổi mỗi lần; hạn mức Kaggle đang hết. Mỗi lần xin địa chỉ mới là một lần gián đoạn.
- **Vì sao mức 1.** Không có nó thì TC-3 mãi ở trạng thái tắt và báo cáo không có bảng trước/sau.
- **Rủi ro lớn nhất của cả lộ trình.** Nếu tới 01/12 vẫn không có GPU: bảng trước/sau chỉ còn phần đo được không cần GPU (kiểm chứng trên câu trả lời đã lưu, bộ giả `run_l1.py`), TC-3 nộp ở trạng thái tắt kèm kết quả trên bộ giả. Cần phương án GPU thay thế (quyết định 3).
- **Xong khi.** Có hai bảng trước và sau trên cùng bộ câu hỏi, mỗi lần so chỉ đổi một yếu tố, kèm số lần gọi và chi phí.

#### DG-3. Đưa ca P0 vào `backend/tests/` · Mức 2

- **Làm gì.** Ca đang đạt vào làm test hồi quy; ca đang trượt vào dưới dạng "biết trước là trượt" (`xfail(strict=True)`), để khi sửa xong test tự đổi màu. Ca gọi mô hình thật ở lại `experiments/`.
- **Vì sao làm.** TC-1 đến TC-5 sửa đúng các hành vi này. Không có test hồi quy thì một sửa sau có thể làm hỏng lại sửa trước mà không ai biết.
- **Trạng thái.** Sinh viên đã nói "chưa làm vội" ngày 13/11. Đề xuất xem lại: làm **cùng lúc** với từng việc TC (mỗi việc mang theo ca của nó), thay vì một đợt riêng. Xem quyết định 5.

#### DG-4. So sánh với NotebookLM và báo cáo thử tấn công · Mức 2

- **Làm gì.** 10 câu hỏi giống nhau hỏi FinHelp và NotebookLM trên cùng PDF, chấm tay. Một báo cáo thử tấn công dựa trên bộ guard đã đo.
- **Vì sao mức 2.** Câu hỏi "khác NotebookLM ở đâu" gần như chắc chắn được hỏi khi bảo vệ, và 10 câu chấm tay là bằng chứng rẻ. Nhưng nó không làm sản phẩm tốt hơn, nên đứng sau luồng TC.

### Luồng GD: giao diện

#### GD-1. Chạy trọn luồng chính trong ứng dụng thật · Mức 1

- **Làm gì.** Với backend và cơ sở dữ liệu phát triển đang chạy: đăng ký, tải một PDF, hỏi, bấm trích dẫn, xem dải tô sáng, hỏi nối tiếp. Ghi lại lỗi gặp phải. Kiểm luôn lỗi cũ số 6 (PDF bị tải lại mỗi lần bấm trích dẫn) còn hay không.
- **Vì sao mức 1.** F9 mới chỉ được kiểm trên trang thử riêng, không qua backend. Đây là điều kiện 1 của MVP và chỉ tốn nửa ngày. Phần cần bộ lập kế hoạch và máy GPU thật thì làm trong DG-2.
- **Xong khi.** Một lượt chạy trọn không lỗi, có ảnh chụp màn hình dùng luôn cho báo cáo.
- **Một lượt đầu chạy 13/11 trên đường local** (backend dùng mô hình trên máy, dữ liệu `datn_dev`, tài khoản thử tạo riêng; 4 lời gọi DeepSeek trên 8 được duyệt): tải `ULTABEAUTY_2023Q4_EARNINGS.pdf` (9 trang, 97 KB) → **nạp xong sau 106 giây** (Docling 41 giây, khởi động Docling 36 giây, nạp BGE-M3 16 giây; 10 đoạn trích; danh mục đúng: Ulta Beauty, FY2022, quý 4). Hỏi "What was Ulta Beauty's net income in the fourth quarter of fiscal 2022?" → trả lời đúng **$340,8 triệu** ($340.751 nghìn) sau **19,9 giây** (lập kế hoạch 14,2 giây gồm cả nạp lại reranker lần đầu, tìm 0,7 giây, viết 1,6 giây; 3 lời gọi, 8.410 token; guard "ok" 1,25 giây; kiểm chứng đạt, không phải sửa). Mở giao diện, đăng nhập, sổ tay và lịch sử hiện đúng; bấm trích dẫn [2] mở PDF đúng trang 6, banner "Citation verified on page: Page 6" và "Marked 9 line(s) of the excerpt on this page", các dải tô hiện đúng dòng.
  - **Hạn chế đó đã sửa cùng ngày (commit `f91c398`), theo yêu cầu của sinh viên:** khung "Citation verified" kèm bảng Markdown của đoạn trích đã bỏ; giao diện chỉ còn PDF có tô vàng. Khung nhỏ chỉ hiện khi có điều cần nói (tài liệu được trích đã bị xóa, hoặc trang không tô được vì là trang quét hay xoay ngang). Thêm tô **đậm hơn** các dòng chứa con số mà câu trả lời nêu cạnh dấu [n] (`citedFigures` lấy số trong câu hoặc ô bảng có [n], bỏ năm và số nhỏ; `figureLines` tìm cả dòng chứa số đó trên trang, tối đa 3 chỗ mỗi số). Kiểm trên trình duyệt với đúng câu trả lời Ulta: trang 6 tô đậm dòng "Net income" 340,751, trang 1 tô đậm tiêu đề "Net Income of $340.8 Million"; các dòng của đoạn trích vẫn tô nhạt hơn. `tsc`, `vite build` và `npm run test:highlight` (thêm 2 ca) đều qua.
  - **Chưa chạy:** hỏi nối tiếp, so sánh hai công ty (cần thêm một tài liệu và thêm lời gọi), lỗi máy GPU hoặc mô hình ngôn ngữ trong ứng dụng thật.
- **Đường local (kiểm 13/11, vì chưa mở được máy GPU từ xa).**
  - **Mã giống nhau.** Hai đường dùng chung mã backend; chỉ khác ba chỗ rẽ nhánh theo `REMOTE_GPU_URL`: vector hóa, chấm lại, và Docling. Đã đối chiếu với notebook worker: phần postprocess nhúng trong notebook **giống từng byte** `backend/app/modules/ingestion/postprocess/`; câu lệnh và tiền tố của reranker, độ dài tối đa, cách tính điểm, tham số vector hóa, tùy chọn Docling (không OCR, bảng chính xác) đều giống. Khác biệt duy nhất về hành vi: khi postprocess lỗi, worker dùng Markdown thô của Docling còn đường local rơi về PyMuPDF cho cả tài liệu. Bước lập danh mục dùng API DeepSeek nên không phụ thuộc đường nào. Phần chỉ khác về cấu hình chạy (kích thước lô, số GPU) không tính, theo yêu cầu.
  - **Chạy được, có một lỗi môi trường.** Máy có RTX 3050 Ti 4 GB; hai mô hình có sẵn trong `backend/storage/models/`. Từng mô hình chạy riêng đều tốt (vector hóa 1024 chiều, chấm lại cho điểm hợp lý). Nhưng **nạp reranker sau BGE-M3 trong cùng một tiến trình làm tiến trình chết (segfault, mã 139)**, ở cả ba chế độ GPU (`auto`, `swap`, và có `HF_DEACTIVATE_ASYNC_LOAD`); nạp reranker trước rồi BGE-M3 thì chạy ổn. Bộ nhớ ảo Windows lúc đó còn 16,7 GB nên không phải lỗi hết bộ nhớ như lần ghi trong `version_control.md` dòng 123. Chưa rõ nguyên nhân gốc. Cách tránh đang dùng: một file khởi động ngoài kho mã nạp reranker trước rồi chạy backend. Nếu muốn sửa trong mã, chỗ hợp lý là `warm_models` (nạp reranker trước, và bật `PRELOAD_MODELS` khi chạy local); cần bạn duyệt.
  - **Cẩn thận khi tự viết lệnh khởi động.** `backend/.env.dev` chỉ có tác dụng nếu được nạp **trước** khi `app.core.config` được import; nạp muộn thì backend nối vào dữ liệu thật (Atlas, collection `financial_chunks_m3`). Lần khởi động thử đầu tiên mắc lỗi này (không tải gì lên, không hỏi gì; đã kiểm bằng truy vấn chỉ đọc: 6 job và 6 tài liệu thật giữ nguyên trạng thái); file khởi động nay kiểm tên cơ sở dữ liệu trước khi nạp mô hình và dừng nếu không phải `datn_dev`.


#### GD-2. Hiện trạng thái bằng chứng trên giao diện · Mức 2

- **Làm gì.** Backend đã trả `answer_meta` với ba trạng thái: đã trả lời, một phần, không tìm thấy. Giao diện chat hiện một nhãn nhỏ tương ứng trên mỗi câu trả lời.
- **Vì sao làm.** Mọi công sức của luồng TC là vô hình với người dùng nếu câu trả lời "một phần" trông y hệt câu trả lời đầy đủ.
- **Vì sao mức 2.** Dữ liệu đã có sẵn, chỉ là phần hiển thị (1 ngày), và nó làm buổi demo thuyết phục hơn. Nhưng thiếu nó câu trả lời vẫn đúng.
- **Mở rộng sau MVP.** Sáu trạng thái của `tối ưu.txt` (thêm: không tìm thấy khi tìm, nguồn không công bố, nguồn không dùng được, bằng chứng mâu thuẫn), cần TC-3 và TC-5 xong trước.

### Luồng DA: đồ án

#### DA-1. Nội dung 6: kịch bản demo chạy trọn · Mức 1

- **Quyết định của sinh viên (13/11).** Không cần người dùng thật, không cần mở ra mạng; chỉ cần demo được. Phần "thử nghiệm với bộ dữ liệu thật" của mẫu phiếu được đáp ứng bằng FinanceBench 150 câu và bộ 200 câu nhiều tài liệu (DG-1).
- **Làm gì.** Viết một kịch bản demo 8 đến 10 phút và chạy thử hai lần trước ngày bảo vệ: tải báo cáo, hỏi một câu số liệu, bấm trích dẫn (tô sáng), hỏi nối tiếp, hỏi so sánh hai công ty, một câu bị từ chối, một câu có phép tính, trang quản trị. Chuẩn bị sẵn tài liệu đã nạp để không chờ bóc tách trên sân khấu, và một phương án khi máy GPU hoặc mạng hỏng.
- **Vì sao mức 1.** Vẫn là điều kiện bảo vệ, nhưng chỉ còn khoảng nửa ngày. Phụ thuộc GD-1 (luồng chạy trọn) và DG-2 (số liệu để đưa vào demo).
- **Xong khi.** Chạy trọn kịch bản hai lần không lỗi, có ảnh chụp và bản ghi hình dự phòng.
- **Nếu sau này đổi ý (mở ra mạng, thu phản hồi).** Cần thêm VH-4 (trang riêng tư), VH-3 (Docker một lệnh) và ít nhất 2 đến 3 ngày công; xem mục 8, hướng 6.

#### DA-2. Báo cáo, slide, video demo (mã cũ F12) · Mức 1

- **Làm gì.** Viết song song từ tuần 1, không dồn vào tuần cuối. Mỗi việc TC xong thì viết luôn đoạn tương ứng khi số liệu còn mới.
- **Lưu ý.** Không đưa con số nào chưa có nguồn đo vào báo cáo. Điền file phiếu giao nhiệm vụ (hiện còn là mẫu trống).

#### DA-3. Vẽ lại sơ đồ thiết kế cho đúng code · Mức 2

- **Làm gì.** Bốn sơ đồ trong `docs/Version_2/diagrams/` vẽ theo trạng thái 07/11: chưa có lớp guard, luồng SSE, trang quản trị. `ARCHITECTURE.md` đã đúng; cập nhật sơ đồ theo nó.
- **Vì sao mức 2.** Báo cáo cần sơ đồ đúng, nhưng có thể dùng sơ đồ sinh từ `ARCHITECTURE.md` nếu hết thời gian.

---

## 6. Thứ tự làm, từ 14/11 đến 10/12

Nguyên tắc xếp: việc ngoại tuyến và việc mở khóa cho việc khác đi trước; việc cần GPU gom vào một đợt ở tuần 3; hai ngày cuối không viết code mới.

| Tuần | Ngày | Kỹ thuật | Song song (sinh viên) | Điểm dừng báo cáo |
|---|---|---|---|---|
| 1 | 14 đến 20/11 | **VH-1** → **TC-2** → **TC-1** → **GD-1** | Chấm 200 câu nhiều tài liệu (xong khoảng 22–23/11). Dựng khung báo cáo (DA-2). | Sau VH-1; sau TC-1 |
| 2 | 21 đến 27/11 | **DG-1** (khung với FinanceBench trước, 200 câu nhiều tài liệu khi chấm xong) → **TC-3** (phần code, cờ tắt) → **TC-4** | Viết chương thiết kế. Tìm nguồn GPU (quyết định 3). | Sau DG-1; sau TC-4 |
| 3 | 28/11 đến 04/12 | **DG-2** (đợt đo) → **DA-1** → mức 2 theo thứ tự: TC-5, VH-2, GD-2, DG-3 | Viết chương đánh giá ngay khi có bảng. Tập dượt demo (DA-1). | Sau DG-2 |
| 4 | 05 đến 10/12 | Chỉ sửa lỗi phát hiện khi demo thử. Đóng băng code ngày 08/12. | **DA-2**: hoàn thiện báo cáo, slide, quay video. DA-3. | 08/12 |

**Phụ thuộc cần nhớ:** VH-1 trước VH-2 và VH-3. TC-2 trước DG-2. DG-1 trước DG-2. TC-3 (code) trước DG-2 (đo ngưỡng). TC-4 trước GD-4. Quyết định 2 trước DA-1.

**Thứ tự cắt khi trễ.** Cắt từ trái sang phải; không bao giờ cắt việc mức 1:

GD-4 → GD-3 → VH-5 → TC-7 → TC-6 → VH-3 → DG-4 → DA-3 → GD-2 → VH-2 → DG-3 → TC-5.

Nếu chính một việc mức 1 trễ: thu hẹp **phạm vi** của nó chứ không bỏ. TC-4 còn 8 chỉ tiêu thay vì 15 đến 20. TC-3 nộp ở trạng thái tắt kèm số đo. DG-1 còn 30 câu, bỏ phần ca dữ liệu thiếu. DA-1 dùng cách B.

---

## 7. Quyết định đang chờ sinh viên

Xếp theo mức gấp. Ba quyết định đầu chặn việc của tuần 1 và 2.

| # | Quyết định | Vì sao phải quyết | Đề xuất |
|---|---|---|---|
| 1 | **Duyệt sửa `backend/` cho TC-2 và TC-1** | Đây là hai việc kỹ thuật đầu tiên; không duyệt thì tuần 1 chỉ làm được VH-1. | Duyệt. Cả hai có ca test sẵn để đo trước và sau, không cần GPU hay tiền. |
| 2 | ~~Nội dung 6: mở ra mạng hay chỉ demo~~ | **Đã quyết 13/11: chỉ cần demo được, không cần người dùng thật.** | Giữ. DA-1 thu còn nửa ngày; VH-3 và VH-4 ở mức 2 và 3. |
| 3 | **Nguồn GPU cho đợt đo DG-2** | Hạn mức Kaggle đã hết; đây là rủi ro lớn nhất về tiến độ. | Biết ngày hạn mức Kaggle có lại; chuẩn bị sẵn `colab_gpu_worker.ipynb` làm phương án hai. Cần chốt trước 27/11. |
| 4 | **Ngày bảo vệ và định nghĩa MVP ở mục 2** | Cả lịch dựa trên mốc 10/12 "dự kiến" và 6 điều kiện tôi đề xuất. | Xác nhận hoặc sửa. |
| 5 | **Đưa ca P0 vào `backend/tests/` cùng lúc với từng sửa (DG-3)** | Bạn đã nói "chưa làm vội". Nhưng sửa mà không có test hồi quy thì dễ hỏng lại. | Đổi thành: mỗi việc TC mang theo ca của chính nó. Không làm một đợt riêng. |
| 6 | **LangGraph hay vòng lặp viết tay** (còn mở từ 13/11) | Không chặn MVP. | Để sau MVP. TC-3 là vòng lặp tối đa một lần, viết bằng code thường là đủ. Xét lại khi làm câu hỏi nhiều bước (mục 8, hướng 1). |
| 7 | **Câu hỏi khái niệm tài chính trả lời từ kho tri thức** (còn mở, nghiêng 70 % có) và bản quyền giáo trình CFA | Không chặn MVP: TC-4 không cần kho tri thức. | Để sau MVP. Giữ chính sách từ chối nhất quán hiện tại. |

Các quyết định đã chốt ngày 13/11 và vẫn giữ: không đưa `docs/Version_3/` và `experiments/p0_suite/` vào git; giữ mô hình suy nghĩ cho bước trả lời và bước lập kế hoạch; giữ DeepSeek (đã thử một mô hình khác, không tốt hơn); không dùng Redis, không dùng cây tin nhắn, không dùng TanStack Query trước bảo vệ.

---

## 8. Mở rộng sau MVP: làm gì, vì sao, cần gì trước

Mỗi hướng ghi rõ nó dựng trên việc nào của MVP, để thấy vì sao thứ tự hiện tại là đúng.

| # | Hướng | Làm gì | Vì sao đáng làm | Cần xong trước | Vì sao không làm bây giờ |
|---|---|---|---|---|---|
| 1 | **Câu hỏi nhiều bước** | Thay câu từ chối `not_supported_yet` bằng tối đa 2 bước nối nhau (ví dụ "công ty nào doanh thu cao nhất, và lợi nhuận của công ty đó"). Có thể bọc luồng hỏi đáp bằng LangGraph. | Đây là loại câu NotebookLM hay sai và là điểm demo rõ nhất của hướng agent. | TC-3 (vòng tìm lại), DG-1 (bộ đo) | Chưa có vòng lặp nền; thêm bước là thêm chỗ sai khó đo. |
| 2 | **Kho tri thức khái niệm** | Một sổ tay chung do quản trị viên nạp giáo trình; câu "ROE là gì" được trả lời có trích dẫn. | Hiện các câu này bị từ chối; với người học tài chính đó là nhu cầu thật. | TC-4, quyết định 7, bản quyền | Cần mã hóa vector (GPU) và một chính sách quyền xem mới. |
| 3 | **Số liệu có cấu trúc** | Đọc XBRL của SEC (thư viện `edgartools`) để có bảng số chuẩn theo chỉ tiêu, kỳ, đơn vị; truy vấn bảng bằng SQL. | Xóa tận gốc lỗi đọc nhầm cột, nhầm đơn vị mà TC-1 chỉ bắt được một phần. | TC-1 (đo được lỗi cột nhiều tới đâu) | Phải đổi khâu nạp tài liệu; chỉ áp dụng cho hồ sơ SEC. |
| 4 | **So sánh rộng** | 5 đến 10 công ty, nhiều năm, GAAP và non-GAAP, nhiều đơn vị tiền tệ (nhóm P1 của `tối ưu.txt`). | Mở rộng phạm vi phân tích thật. | TC-3, TC-5 | Mỗi công ty thêm là thêm chỗ thiếu bằng chứng; cần TC-3 chạy ổn trước. |
| 5 | **Tiếng Việt** | Đo câu hỏi tiếng Việt; bộ lập kế hoạch trả thêm câu hỏi dịch sang tiếng Anh cho nhánh nhiều tài liệu; tên công ty Việt. | Người dùng mục tiêu ban đầu hỏi bằng tiếng Việt. | DG-1 | Đã quyết "tiếng Anh trước" để giữ mốc đo. |
| 6 | **Vận hành thật** | Triển khai công khai ổn định; giới hạn tần suất dùng chung nhiều tiến trình (Redis); thanh hạn mức token theo ngày; chặn gửi trùng; cờ suy giảm; dấu vết đầy đủ (mã băm prompt, điểm từng đoạn trích). | Cần khi có nhiều người dùng đồng thời. | VH-1, VH-3, VH-4 | Một tiến trình, ít người dùng thì chưa cần. |
| 7 | **Tốc độ** | Câu trả lời dài mất khoảng 23 giây, phần lớn là mô hình suy nghĩ. Hướng thử: định dạng "tính trước, kết luận sau" khi tắt suy nghĩ; bộ nhớ đệm khớp chính xác. | Thời gian chờ là than phiền dễ gặp nhất. | DG-1 | Tắt suy nghĩ đã đo làm độ đúng giảm từ 27/30 xuống 12/30; mọi thay đổi ở đây phải đo lại. |
| 8 | **Khâu nạp tài liệu** | Tiêu đề ngữ cảnh cho mỗi đoạn trích; thử bộ bóc tách nhanh hơn Docling (pdfplumber giai đoạn 2, xberg); nhận diện công ty đổi tên qua mã CIK của SEC; định tuyến theo mục của 10-K. | Docling mất 0,74 giây mỗi trang trên GPU; đoạn trích bảng thiếu tên công ty và năm. | DG-1 | Đổi khâu nạp là phải nạp lại và đo lại toàn bộ. |
| 9 | **Hiểu câu hỏi** | Nhãn loại câu hỏi (tra số, so sánh, tính toán, diễn giải); chính sách "tìm rồi mới hỏi lại"; sáu trạng thái bằng chứng. | Hỏi lại đúng lúc, không hỏi thừa. | GD-2, TC-3 | Mô hình đang tự xử lý ổn các ca đã đo (A04). |

---

## Phụ lục A. Trạng thái các hạng mục theo mã cũ

Giữ để tra ngược từ tài liệu khác. Quy ước: ✅ xong · 🚧 đang dở · ⬜ chưa làm · ↪ đã đổi hướng.

| Mã cũ | Hạng mục | Trạng thái | Ghi chú (đối chiếu 13/11) | Mã mới |
|---|---|---|---|---|
| F-1 | Chuẩn hóa `.env.example`, dọn schema | ✅ 28/10 | File có trên máy nhưng **bị git bỏ qua**. | VH-1 |
| F0 | Nhánh git, hạ tầng | ✅ 07/11 | MongoDB 7.0, Qdrant v1.19.2 trong Docker Compose. | |
| F1 | Tái cấu trúc backend thành module | ✅ 07/11 | 9 module trong `backend/app/modules/`. Còn sót thư mục cũ `backend/app/services/` (có `email_service.py`). | |
| F2 | Bộ đánh giá trong `backend/evaluation/` | ⬜ | Thư mục chưa tồn tại. | DG-1 |
| F3 | Router frontend, trang giới thiệu, danh sách sổ tay | ✅ | TanStack Query: ↪ không làm. | |
| F3.5 | Cấu trúc MongoDB V3.1 | 🚧 | Nhánh `feat/mongodb-v3-schema` đã gộp vào `main`. Chưa xác minh việc chuyển đổi đã chạy trên cơ sở dữ liệu thật. | VH-1 (bước 5) |
| F4 | Hội thoại nối tiếp, báo câu trả lời sai | ✅ | Đã ở `origin/main`. Chưa làm: gợi ý câu hỏi sinh theo chỉ tiêu (hiện 3 gợi ý cố định). | GD-3 |
| F5 | Trả lời dạng dòng chảy (SSE), tiến trình | ✅ | `POST /chat/query/stream`. | |
| F6 | Redis và hàng đợi `arq` | ↪ | Giữ job trong MongoDB. Giới hạn tần suất lưu trong bộ nhớ một tiến trình. | Mục 8, hướng 6 |
| F7 | Quên mật khẩu qua email | ✅ | Không chạy thử lại. Mẫu email **bị git bỏ qua**. | VH-1 |
| F8 | Cloudflare R2 | ✅ | Không chạy thử lại. | |
| F9 | Tô sáng trích dẫn trên PDF | ✅ 13/11 | Commit `10422a0`. 303/304 dòng được tìm thấy trên 27 trang bảng thật. Chưa chạy trong ứng dụng thật qua backend. Trang quét ảnh hoặc xoay ngang thì không tô được. | GD-1 |
| F10 | Trang quản trị | ✅ | Commit `2fb1cd9`. | |
| F11 | Quan sát, Docker, CI | ⬜ | `/health` đã thử kết nối thật. Chưa có CI, README, `nginx.conf`. | VH-1, VH-2, VH-3 |
| F12 | Chuẩn bị bảo vệ | ⬜ | | DA-2 |
| G1 | Lớp guard an toàn | ✅ | Commit `a0ca4b5`. | |
| G2 | Kiểm chứng phép tính và con số bằng code | ✅ | Commit `93ad4ee`, `922d38f`. | Nền của TC-1, TC-4 |
| G3 | Lưới an toàn cho câu hỏi nhiều tài liệu | ✅ | Commit `3ef849b`. | Nền của TC-3 |
| P0 | Bộ test hành vi P0 | ✅ trừ D03 | 23 ca; chưa vào `backend/tests/`. | DG-2, DG-3 |
| B1 đến B5, C1, C2 | Các sửa theo bảng điểm P0 | ⬜ | | TC-2, TC-3, TC-5, TC-6, TC-1, TC-4; C2 ở mục 8, hướng 2 |

## Phụ lục B. Tài liệu thiết kế trong `docs/Version_2/`

- `diagrams/`: sơ đồ use case tổng quan, kiến trúc, pipeline RAG, ERD, và `diagrams_viewer.html`. **Vẽ theo trạng thái 07/11**, chưa có lớp guard, SSE, trang quản trị (việc DA-3).
- `use_cases/01` đến `06`: đặc tả use case theo sáu phân hệ (xác thực, nạp tài liệu, hỏi đáp, trích dẫn và kiểm chứng, sổ tay, quản trị).
- `SYSTEM_ARCHITECTURE_V2.md`, `PILLAR_2_MONGODB_SPECIFICATION.md`: thiết kế V2. Kiến trúc đúng với code hiện tại là `ARCHITECTURE.md` ở thư mục gốc.
