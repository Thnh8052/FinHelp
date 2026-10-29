# Ý nghĩa: tỉ lệ chiều cao (phần đuôi / chữ hoa đầu) từ đó trở xuống coi là small caps.
# Giữ vì: đo trên MGM/AES: small caps 0.69-0.77, chữ hợp lệ ("I CONDENSED", "B II", "I LLC", "J M") đều 1.0; 0.9 nằm giữa hai nhóm.
SMALL_CAPS_MAX_RATIO = 0.9


# Ý nghĩa: số chữ hoa đơn liên tiếp tối thiểu để coi là một từ giãn cách chữ ("I N D E X").
# Giữ vì: 3 chữ hoa đơn còn gặp ở chữ viết tắt hợp lệ ("A B C"); đo trong dữ liệu chỉ có một ca thật (MGM p172, 5 chữ).
LETTER_SPACED_MIN_RUN = 4


# Ý nghĩa: chữ (đã chuẩn hóa) của header điều hướng không cần liên kết để nhận ra.
NAV_TITLE_KEY = "TABLEOFCONTENTS"


# Ý nghĩa: số trang tối thiểu trong một tài liệu mà cùng một dòng đầu trang lặp lại thì mới coi là header chạy.
# Giữ vì: đo trên 84 PDF eval_84: header "Table of Contents" thật lặp 80-133 trang; trang mục lục thật chỉ lặp 2-4 trang (Walmart 2018, CVS,
#   American Water Works, PepsiCo 8K) nên ngưỡng 5 loại được chúng; hạ xuống 2 sẽ xóa nhầm tiêu đề thật.
NAV_HEADER_MIN_PAGES = 5


# Ý nghĩa: một kiểu chữ tiêu đề chỉ tạo ra một cấp riêng khi có ít nhất HEADING_STYLE_MIN_COUNT tiêu đề và HEADING_STYLE_MIN_SHARE tổng số
#   tiêu đề có kiểu chữ; kiểu chữ hiếm hơn (tiêu đề trang bìa, đồng cỡ lẻ) được gộp vào kiểu chữ phổ biến gần nhất (cỡ, rồi bold, rồi nghiêng).
# Giữ vì: không gộp thì AMCOR có 8 cấp (2 kiểu chữ trang bìa chen lên trên nhóm rủi ro), JPM 18 cấp; Markdown chỉ có 6 cấp.
HEADING_STYLE_MIN_COUNT = 3


HEADING_STYLE_MIN_SHARE = 0.03
# Ý nghĩa: các từ có đáy trên cách từ cao nhất không quá ngần này điểm PDF thuộc cùng "dòng chữ trên cùng" của trang.
TOP_LINE_TOLERANCE = 3


# Ý nghĩa: dòng bắt đầu bằng các ký hiệu này là heading, hàng bảng hoặc khối mã, không phải đoạn văn.
# Giữ vì: không bao giờ nối các dòng cấu trúc, cả khi PDF cho thấy cùng dòng.
STRUCTURE_PREFIXES = ("#", "|", "```")


# Ý nghĩa: ký hiệu đầu mục danh sách đứng một mình; dấu câu mở đầu từ small caps; dấu câu cuối từ.
BULLET_TOKENS = frozenset({"-", "*", "•", "–", "—", "·", "+"})


LEADING_PUNCT = "(\"“["
TRAILING_PUNCT = ",.;:)\"”]!?"
# Ý nghĩa: ô chỉ có ký hiệu đứng trước số trong bảng số liệu: tiền tệ và dấu hạng ("#" của bảng xếp hạng JPM p72).
# Giữ vì: đo trên 10 tài liệu, 27 cột bản sao có cột kề trái không chữ số; giá trị của các cột đó: "$" 92, "#" 2, ngoài ra "High" (hàng
#   header lặp trong thân, AMD p32) và "-" (AMD p57). "%" và ")" không có vì đứng SAU số, nhãn đã ở cột số.
SYMBOL_CELLS = frozenset("$€£¥#")


# Ý nghĩa: ký hiệu đứng TRƯỚC giá trị ("$", "(") dính vào từ kế tiếp, ký hiệu đứng SAU ("%", ")") dính vào từ liền trước khi gom từ PDF thành giá trị.
VALUE_PREFIXES = SYMBOL_CELLS | {"("}


VALUE_SUFFIXES = frozenset({"%", ")", "%)"})
# Ý nghĩa: khoảng cách PDF (điểm) tối đa giữa hai khoảng chữ liền nhau mà vẫn là cùng một cột giá trị (lỗi 12).
# Giữ vì: dấu cách giữa hai từ cùng ô khoảng 0,25 cỡ chữ (2-2,5 điểm ở chữ 8-10 điểm) và chỉ số chú thích nhỏ đứng sát số, còn hai cột
#   giá trị liền nhau cách từ 3,4 điểm (JPM, bảng nén chặt); 3 là giá trị cho nhiều bảng được dựng lại nhất (751/902 bảng số liệu; 0,5: 732, 5: 712).
VALUE_GAP_TOLERANCE = 3.0


# Ý nghĩa: các từ của một hàng giá trị có tâm dọc lệch nhau quá ngần này (điểm) là thuộc hai dòng chữ khác nhau (Docling gộp hai hàng làm một).
# Giữ vì: hàng bị gộp lệch 7,3-22 điểm (đo 41 bảng, một dòng chữ 8-10 điểm); các từ cùng một dòng lệch tâm dưới 1 điểm.
VALUE_LINE_TOLERANCE = 4.0


# Ý nghĩa: tỉ lệ ô giá trị tối thiểu phải là "số" (mọi từ có chữ số, ký hiệu hoặc gạch) để bảng được dựng lại cột.
# Giữ vì: bảng chữ (phụ lục, danh sách lãnh đạo, mô tả hợp đồng) có ô giá trị là câu dài; chỉ bảng có cột số cần dựng lại. Đo: 0,8 dựng lại 103
#   bảng, 0,5 thêm 4 bảng chữ lẫn số (AMD p75 "$ 6,478" | "2016 to 2035", JPM p276 "%"), hạ nữa không thêm bảng nào.
NUMERIC_TABLE_MIN_SHARE = 0.5


# Ý nghĩa: Docling ghi mọi gạch ngang/trừ và nháy cong trong ô bảng bằng ký tự ASCII (nháy kép cong thành nháy đơn); chữ lấy từ PDF phải qua cùng phép đổi.
# Giữ vì: 0 ký tự "—" "–" "−" trong 15.530 dòng bảng của output/ dù PDF in "—" (AES p134 "—", Docling "-"); ô bảng có 508 nháy đơn và 10 nháy kép,
#   (“EMEA”) của PDF (JPM p35) thành ('EMEA').
TEXT_FOLD = str.maketrans("—–−’‘“”", "---''''")


# Ý nghĩa: lý do `value_words` bỏ qua bảng khi hàng của Docling không khớp dòng chữ PDF: giá trị nằm sai hàng (`tokens`), hàng gộp hai dòng chữ
#   (`multiline`), từ PDF nằm ngoài mọi hàng (`stray_word`). Chỉ các lý do này mới thử dựng lại hàng từ dòng chữ PDF (lỗi 13).
# Giữ vì: `span` (ô gộp trong thân) không phải lỗi hàng; đo 46 bảng: multiline 30, tokens 15, stray_word 1.
ROW_MISMATCH = ("tokens", "multiline", "stray_word")


# Ý nghĩa: sai số ngang (điểm) khi xếp một từ nhãn vào cột nhãn: từ thuộc cột nhãn cuối cùng có mép trái ô Docling không lớn hơn x0 của từ cộng ngần này.
# Giữ vì: chữ của một cột nhãn bắt đầu đúng mép trái ô Docling của cột đó (chữ thụt vào thì x0 lớn hơn nên vẫn ở cột đó); hai cột nhãn cách nhau hàng chục điểm.
LABEL_COLUMN_TOLERANCE = 2.0


# Ý nghĩa: một dòng chữ nối tiếp (ô chữ xuống dòng) nằm giữa hai dòng hàng chỉ thuộc dòng hàng bên dưới khi cách nó gần hơn dòng hàng bên trên ít nhất ngần này
#   (điểm); chênh ít hơn thì thuộc dòng bên trên (chữ căn đầu ô, cách xếp thường gặp nhất).
# Giữ vì: ô căn đầu có dòng nối tiếp cách dòng trên 6,7-8,3 điểm còn cách hàng kế 9,3-10,3 (AES p14); ô căn giữa có dòng nối tiếp cách dòng trên 10,1-10,5 và
#   cách dòng có số 6,9-7,0 (AMCOR p79), 12,0 và 9,6 (AMD p51): chênh từ 2,4 điểm trở lên.
BOUNDARY_MARGIN = 1.5


# Ý nghĩa: hai từ cùng dòng cách nhau không quá ngần này (điểm) thì thuộc cùng một cụm chữ (một ô); cụm gồm toàn số hoặc từ giữ chỗ là ô số, cụm còn lại là ô chữ.
# Giữ vì: dấu cách giữa hai từ cùng ô khoảng 2-3 điểm (như VALUE_GAP_TOLERANCE), hai cột liền nhau của bảng chữ cách nhau xa hơn nhiều.
PHRASE_GAP = 6.0


# Ý nghĩa: ký tự có thể có trong một số thuần (chữ số, dấu phẩy, chấm, phần trăm, ngoặc, gạch, ký hiệu tiền).
NUMBER_CHARS = frozenset("0123456789,.%()-") | SYMBOL_CELLS


# Ý nghĩa: hai bảng ở cuối trang N-1 và đầu trang N chỉ là một bảng khi mép trái và mép phải của chúng lệch nhau không quá ngần này (điểm) (lỗi 14).
# Giữ vì: đo 6 bảng vắt trang không lặp header (BestBuy 2017 và 2019, CVS 2018, Walmart 2018/2019/2020): lệch mép <= 2 điểm (cùng lề trang, cùng cột).
CONTINUED_EDGE_TOLERANCE = 10.0


# Ý nghĩa: sai số (điểm) khi xét một phần tử trang nằm "dưới" hay "trên" một bảng: hộp bao Docling của bảng và của chữ sát nhau chồng nhau vài phần điểm.
CONTINUED_VERTICAL_SLACK = 2.0


# Ý nghĩa: nhãn Docling của dòng chữ chạy đầu/cuối trang; không chắn giữa hai bảng liền nhau qua trang.
FURNITURE_LABELS = frozenset({"page_header", "page_footer"})


# Ý nghĩa: chữ báo "tiêu đề này là phần tiếp" (lỗi 15): tiêu đề gắn thêm "(continued)" và tiêu đề đã có chữ này (in sẵn trong PDF) không gắn lần nữa.
# Giữ vì: đúng chữ SEC in ("Consolidated Statements of Cash Flows (continued)", PepsiCo 2023Q1 p7) và đúng dấu hiệu `financial_chunker.stitcher.is_section_continuation` nhận.
CONTINUED_WORD = "continued"


# Ý nghĩa: từ (đã bỏ dấu câu hai đầu, in hoa) cho biết một dòng `page_header` là tên báo cáo tài chính hoặc phần "Notes to ... Financial Statements" (lỗi 23); mục không có từ nào trong tập này không được khôi phục.
# Giữ vì: đo trên 84 tài liệu, 4.519 mục `page_header` gồm số trang, "Table of Contents", nhãn "Exhibit 21", tên phần ("PART II", "Item", "Page"); chỉ tập từ này tách được tiêu đề báo cáo mà bảng cần để biết nó là báo cáo nào.
#   Mở rộng sang mọi tiêu đề phần (Note 9, Schedule II, tên mục MD&A của JPM) là việc khác: không cùng bằng chứng và kéo theo nhãn rác.
TITLE_WORDS = frozenset({"STATEMENT", "STATEMENTS", "SHEET", "SHEETS"})


# Ý nghĩa: số từ tối đa của ô đầu hàng header đầu tiên để ô đó là TIÊU ĐỀ báo cáo (lỗi 9) chứ không phải nhãn cột nhãn có nhắc tới báo cáo.
# Giữ vì: đo trên 84 tài liệu, ô là tiêu đề báo cáo dài 3-5 từ ("Consolidated Balance Sheets", "Consolidated Statements of Comprehensive Income"); nhãn cột nhãn dài hơn nhiều
#   ("Line item in the Consolidated Balance Sheet in which the hedged item is included" của J&J p61: 14 từ, cùng hàng với hai nhóm cột thật).
CAPTION_MAX_WORDS = 8


# Ý nghĩa: chữ nối các ô của nhiều hàng header thành một ô Markdown (docling-core `HEADER_ROW_SEPARATOR`): "native backend - TTS".
HEADER_SEPARATOR = " - "


# Ý nghĩa: tỉ lệ chữ in đậm (lỗi 14) để coi hàng đầu của bảng chữ vắt trang là hàng dữ liệu: header gốc của bảng >= BOLD_HEADER_MIN, hàng đầu trang sau <= BOLD_DATA_MAX
#   và các hàng thân của trang trước <= BOLD_BODY_MAX.
# Giữ vì: đo 18 ca bảng chữ vắt trang đúng là phần tiếp (danh sách công ty con 3M/BestBuy/Pfizer, mục exhibit Amazon/CVS/MGM/Lockheed, AES p15/p221): header 0,96-1,0,
#   hàng đầu 0-0,09, thân 0-0,11; 38 ca header bảng mới lặp lại có hàng đầu đậm >= 0,8.
BOLD_HEADER_MIN, BOLD_DATA_MAX, BOLD_BODY_MAX = 0.8, 0.2, 0.3


# Ý nghĩa: ký hiệu chú thích đứng đầu một đoạn chú thích ngoài ngoặc đơn, chữ số hay chuỗi "*" (lỗi 17).
FOOTNOTE_SYMBOLS = frozenset("†‡§¶")


# Ý nghĩa: hàng bảng chỉ có một chuỗi chữ là chữ thân bị Docling nuốt vào bảng số liệu (lỗi 17) khi chữ không đậm, có ít nhất PROSE_MIN_WORDS từ, nằm sau một hàng có giá trị, và cỡ chữ PDF lớn hơn
#   cỡ chữ điển hình của bảng ít nhất PROSE_SIZE_MARGIN điểm.
# Giữ vì: đo trên 8.221 hàng một chuỗi chữ của 84 tài liệu: 480 hàng dài từ 8 từ sau hàng có giá trị là mô tả hàng thật ("Adjustments to reconcile net income ...") nên độ dài không đủ; 129 hàng có cỡ chữ lớn hơn từ 1 điểm
#   là nhãn thật ("Foreign Currency:", "Assets", ngày của Adobe) nên cỡ chữ không đủ; chỉ hai điều kiện cùng lúc (cộng không đậm) chọn đúng chữ thân của Walmart 2018 p33 (8,8 pt so với 7,4 pt của bảng; câu 12-15 từ).
PROSE_MIN_WORDS = 8


PROSE_SIZE_MARGIN = 1.0
# Ý nghĩa: chỉ số chú thích in nhỏ sát số (lỗi 16: "(a)" sau "(43)" ở JPM p136, "3" sau "1%" ở Coca-Cola 2017 p47; xem `sits_on`): chữ cao không quá SUPERSCRIPT_RATIO lần chiều cao từ đứng trước,
#   tâm cao hơn tâm từ đó ít nhất SUPERSCRIPT_RAISE điểm, mép trái cách mép phải số không quá SUPERSCRIPT_GAP điểm (`glue_superscripts`).
# Giữ vì: đo trên khoảng 1.800 từ chỉ số (470 trang) của 84 PDF: tỉ lệ cao 0,50-0,85 (đa số 0,65 như JPM; Coca-Cola 0,54; JPM 10-Q 2021 0,81; số thường cùng cỡ chữ là 1,0), nâng 0,4-4,5 điểm (trung vị 2,5), cách số 0-19,99 điểm
#   (chỉ số căn trái ở vị trí cố định còn số căn phải nên số ngắn cách xa: Coca-Cola "2" và "4" cách 11 điểm, JPM "—" và "(g)" cách 14,7 điểm). 0,85 là ngưỡng cao nhất không nhận nhầm: "(47)" của MGM 8-K
#   p6 là số âm in nhỏ ở cột bên cạnh, tỉ lệ 0,86, cách số bên trái 18,8 điểm.
SUPERSCRIPT_RATIO = 0.85


SUPERSCRIPT_RAISE = 0.3
SUPERSCRIPT_GAP = 20.0
