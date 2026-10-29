"""Sửa lỗi văn bản của Docling raw, ghi sang docling_raw/fixed/ (output/ giữ nguyên làm baseline).

Mọi quyết định "nối hay không" dựa vào PDF gốc, không đoán theo hình dạng chữ, không dùng regex. "Bằng chứng PDF" trong file này luôn là
kết quả của PyMuPDF (`fitz`, hàm `page.get_text("words")`: từng từ + hộp bao + số khối/số dòng); Docling không tham gia bước này:
- Lỗi 6 (vỡ từ theo dòng, "ANNUAL  \\nREPORT  \\n..."): hai dòng Markdown được nối khi trong PDF hai từ ở chỗ nối nằm TRÊN CÙNG MỘT
  dòng chữ. Ngắt dòng thật (địa chỉ, chữ ký: từ cuối dòng trước và từ đầu dòng sau ở hai dòng PDF khác nhau) được giữ.
  Cả ngắt dòng cứng (hai dấu cách cuối) lẫn ngắt `\\n` đơn đều qua cùng luật. Mục danh sách (`- `, `1.`, `(a)`, `•`) không bao giờ
  bị nối vào dòng trước trừ khi PDF xác nhận cùng một dòng.
- Lỗi 7 (small caps, "MGM R ESORTS I NTERNATIONAL"), ba bằng chứng theo thứ tự tin cậy:
  (a) cỡ chữ: trong PDF phần đuôi thấp hơn chữ đầu (tỉ lệ <= 0.9; đo 0.69-0.77, còn "I CONDENSED", "B II", "I LLC" là 1.0). Không cần
      từ vựng nên tên chỉ có dạng small caps ("B EMIS") và đuôi trùng từ thông dụng ("F ACT", "P ART") vẫn đúng;
  (b) từ ghép có sẵn trong PDF còn hai phần không kề nhau ("SBU", "JAMES": chính Docling chèn dấu cách);
  (c) phương án cuối, khi lớp chữ PDF có dấu cách thật cùng cỡ ("R EPORT OF INDEPENDENT"): dòng toàn chữ hoa, từ ghép có ở nơi khác
      trong tài liệu và phần đuôi một mình thì không. Bảo thủ: "F ACT" (tài liệu có "act") không nối.
  Chữ giãn cách ("I N D E X"): chuỗi từ 4 chữ hoa đơn trở lên, không dấu câu, không phải một chữ lặp.
- Lỗi 3 (ô gộp bị nhân bản, "| Consolidated Statements of Income | Consolidated Statements of Income | ... | 65 |"): bằng chứng là
  `docling.json`, không phải PDF: `data.grid` của bảng ghi cho MỖI ô lưới `start_col_offset_idx` của ô gốc; ô lưới có cột bắt đầu khác
  cột của chính nó là bản sao do ô gộp ngang. Bảng Markdown được ghép với bảng Docling của trang bằng so khớp nguyên văn các hàng thân;
  không ghép được thì giữ nguyên bảng (đếm vào báo cáo). Không so chuỗi giống nhau giữa các ô liền kề: hai ô khác nhau tình cờ cùng
  chữ ("—", "$") không bị đụng. Ô gộp theo hàng (lặp xuống các hàng dưới) giữ nguyên: mỗi hàng vẫn tự đủ nghĩa.

- Lỗi 4 (header điều hướng "Table of Contents" bị Docling đổi thành "## Table of Contents" hoặc nuốt làm hàng header của bảng): bằng chứng là
  PDF. Dòng chữ trên cùng của trang là header điều hướng khi có chú thích liên kết nội bộ (LINK_GOTO) phủ lên nó, HOẶC chữ chính là
  "Table of Contents" (18/84 PDF eval_84 như 3M, Adobe, Boeing, Lockheed lặp dòng này mà không có liên kết), và chữ đó lặp ở từ
  NAV_HEADER_MIN_PAGES trang trở lên trong tài liệu. Không gỡ mọi dòng đầu trang lặp: tên công ty ("Walmart Inc.", "PepsiCo, Inc. and
  Subsidiaries") là một phần tiêu đề báo cáo. Chỉ ở trang có dòng đó, phần tử đầu tiên của trang Markdown (tiêu đề, hoặc ô của hàng header
  bảng) mà chữ trùng với nó mới bị gỡ. Tiêu đề "Table of contents" thật của trang mục lục (chỉ 1-4 trang trong tài liệu) giữ nguyên.

- Lỗi 5 (mọi tiêu đề đều là "##"): cấp được suy ra, không đoán theo chữ. "PART <số La Mã>" là cấp 1, "Item <số>" là cấp 2 (tên mục bắt buộc
  của mẫu SEC, mà kiểu chữ PDF không tách được: AMCOR "PART I", "Item 1." và "The Company" cùng cỡ cùng bold). Các tiêu đề còn lại xếp
  cấp sau đó theo kiểu chữ của chữ đầu tiên trong PDF (cỡ lớn trước, rồi bold, rồi không nghiêng trước nghiêng). Cấp là hạng liên tục
  của các loại có mặt trong tài liệu; Markdown dùng "#" * (cấp + 1) vì "#" dành cho tiêu đề tài liệu (đúng quy ước "##" = cấp 1 của Docling).

- Lỗi 8 (đoạn văn vắt qua hai trang bị dồn hết về trang đầu, trang sau rỗng): bằng chứng là `docling.json`: mỗi `prov` của một đoạn văn có
  `page_no` và `charspan` (đoạn chữ nằm trên trang đó). `export_to_markdown(page_no=N)` của Docling gán cả đoạn cho trang của prov[0]; ở
  đây đoạn được cắt theo charspan từng trang rồi các trang bị ảnh hưởng được xuất lại bằng chính bộ ghi Markdown của Docling, nên phần
  đầu trang N+1 về lại trang N+1 (đúng vị trí đọc: trước các phần tử khác của trang đó).

- Lỗi 9 (tiêu đề báo cáo và tên công ty bị dán vào header: Corning 2021 p65 "Corning Incorporated and Subsidiary Companies - Year ended December 31, - 2021" lặp ở cả ba cột năm, ô đầu
  "Consolidated Statements of Income - (In millions, ...)"): Docling kéo hộp bao bảng lên trùm dòng tiêu đề in trên bảng nên dòng đó thành hàng header đầu, và bộ ghi Markdown nối ô các hàng header của mỗi cột bằng " - ".
  Bằng chứng là cấu trúc ô trong `docling.json` cộng dòng PDF (không phải chữ của header): hàng header đầu có ô cột 0 chỉ là tên báo cáo (từ statement/sheet, <= CAPTION_MAX_WORDS từ) và ô còn lại là MỘT ô phủ hết các
  cột giá trị, cùng dòng PDF với tiêu đề (`caption_cells`). Nhóm cột thật ("Year ended December 31,", "JPMorgan Chase & Co.") không bị đụng vì hàng của chúng không có ô tiêu đề. Hàng đó được lấy khỏi header bằng
  cách bỏ chữ của nó ở đầu mỗi ô (`strip_captions`, chạy sau `fix_page` nên nhận cả bảng đã dựng lại cột) rồi đặt lên trên bảng (`split_captions`): tiêu đề in đậm thành tiêu đề Markdown (cấp theo kiểu chữ PDF, như lỗi 5/23),
  tên công ty là một dòng chữ thường; đơn vị ở ô đầu và nhóm kỳ giữ nguyên. Làm TRƯỚC `carry_header` để bảng vắt trang kế thừa header đã sạch. Đo trên 84 tài liệu: 12 bảng (báo cáo chính của Corning 2020, 2021, 2022), 0 chữ thêm.

- Lỗi 11 (nhãn cột đi theo ô đầu của ô gộp là cột "$", cột số liệu thật mất tên cột, Corning p40): TableFormer tách "$" khỏi số thành hai
  cột, header "2020" là ô gộp phủ cả hai; lỗi 3 giữ chữ ở ô đầu nên cột số trống tên. Khi cột bản sao ngay sau một cột ký hiệu (ô là "$",
  "€", "£", "¥", "#" chiếm đa số, không có chữ số) và có chữ số, nhãn đi sang cột số và cột ký hiệu bị làm trống. Bằng chứng là
  `docling.json` (ô gộp) cộng nội dung các hàng thân; chỉ xét header, hàng thân không đổi.

- Lỗi 12 (lệch cột, "$" và "%" tách khỏi số, Corning p76 "(13) $" | "148"): TableFormer chia cột theo khoảng trắng nên "$" của năm sau dính vào
  số của năm trước và số ở hàng thưa nằm lệch cột so với header. Bằng chứng là vị trí chữ trong PDF (PyMuPDF `get_text("words")`) cộng hộp bao
  các ô của `docling.json` (xác định hàng và từ nào là chữ nhãn): "$" dính vào số nó đứng trước, các giá trị gom thành cột theo khoảng ngang,
  mỗi nhãn header ghép vào cột gần tâm nhãn nhất (đúng thứ tự, không trùng); cột "$", "%" và cột đệm trống biến mất, cột chỉ số chú thích
  "(1)" ở lại thành cột không nhãn. Chỉ áp dụng cho bảng số liệu khi chữ khớp và nhãn ghép được (xem `regrid_block`); bảng không khớp giữ
  nguyên và được đếm theo lý do. Chạy TRƯỚC lỗi 3 và 11, bảng đã dựng lại không qua hai lỗi đó nữa.

- Lỗi 13 (hàng bị gộp hoặc xé, nhiều giá trị dồn vào một ô: AES p135 "Depreciation and amortization Loss on disposal ..." | "1,053 9"; nhãn
  "Other" / "liabilities:" với số 120 ở hàng dưới): TableFormer không tách hai dòng chữ sát nhau thành hai hàng và gán chữ sai hàng. Bằng
  chứng là vị trí chữ trong PDF: mỗi dòng chữ PDF là một hàng. Khi `value_words` thấy chữ PDF không khớp hàng Docling (giá trị sai hàng, hoặc một hàng
  có số ở từ hai dòng PDF trở lên), bảng số liệu được dựng lại hàng từ dòng chữ PDF (`reflow_rows`): nhãn xuống dòng nối lại khi một ô nhãn Docling có
  đúng chữ ghép đó hoặc dòng kế bắt đầu bằng chữ thường; hai kiểm tra bảo toàn (không từ nào mất hoặc thừa) chặn vùng quét sai. Hàng chỉ có chữ xuống
  dòng (số chỉ ở một dòng) là hàng Docling đúng nên không dựng lại (`regrid_skip_wrapped`: danh sách lãnh đạo, mô tả hợp đồng). Việc chia cột giá trị
  vẫn do lỗi 12 (`regrid_block`); không chắc dòng nào là hàng nào thì giữ nguyên và được đếm theo lý do (`reflow_skip_*`).
- Lỗi 13b (phần mở rộng, AES p14 p16 p29, JPM p265 p121 p183 p295, Corning p108, ...): (1) bảng nhiều cột nhãn: từ nhãn xếp vào cột theo mép trái ô nhãn Docling;
  (2) hàng con "Solar 967" / "Wind 140" (cùng cột số hai lần) là hai hàng, dòng chữ không có số ("Landfill" / "Gas") nối vào hàng kề theo khoảng cách dọc
  (`attach_continuations`); (3) chú thích "(7)" sát nhãn ở lại ô nhãn; (4) giá trị hoặc chữ Docling nhét vào ô header trả về thân bảng (`strip_moved`), số nằm
  nhầm cột nhãn về cột số; (5) header Docling sai số cột chỉ được sửa cho bảng đã dựng lại hàng (`relaxed_names`): nối nhãn bị xé, tách ô gộp hai cột theo chữ PDF.

- Lỗi 14 (bảng vắt trang không lặp header: Best Buy 2017 p18 "| Virginia | 34 | 8 | - |" bị Docling dùng làm header, mất cột "Best Buy Stores"): Markdown bắt buộc có
  hàng header nên Docling lấy hàng đầu của bảng ở đầu trang N làm header dù nó là dữ liệu. Bằng chứng là `docling.json` (vị trí bảng và chữ trên trang) cộng nội dung
  Markdown đã sửa: bảng đầu trang N là phần tiếp của bảng cuối trang N-1 (`adjacent_tables`) khi mép trái/phải của hai bảng trùng nhau và không còn dòng chữ hoặc hình nào
  chen giữa (chú thích dưới bảng trang trước, header điều hướng, đầu/cuối trang chạy thì không tính); hàng đầu là hàng dữ liệu (`is_data_row`: nhãn + số liệu, không có năm),
  cùng số cột, và header của bảng trang trước không phải hàng dữ liệu và có nhãn ở mọi cột có giá trị. Khi đó header trang trước được chép nguyên văn lên trên (`inherit_header`);
  header lấy từ trang đã sửa nên bảng ba trang trở lên kế thừa dây chuyền. Bảng chữ thuần (danh sách công ty con, mục lục) không phân biệt được với header chỉ bằng nội dung nên giữ nguyên.

- Lỗi 15 (bảng vắt trang mất tên bảng: 3M 2018 p9 mở đầu bằng "| Name | Age | Present Position ... |" của danh sách lãnh đạo, còn tiêu đề "Executive Officers" chỉ in ở p8): Docling xử lý từng trang,
  nên chunk bắt đầu ở đầu trang sau chỉ có hàng bảng, embedding và truy xuất không biết đó là bảng gì. Bảng KHÔNG được nối sang trang trước (mỗi trang giữ đúng nội dung của nó: số trang là bằng chứng khi
  đánh giá truy xuất); trang sau được đặt lại tên bảng thành dòng "<tiêu đề> (continued)", cùng số "#" với tiêu đề gốc nên cây tiêu đề không đổi (`carry_title`). Hai bằng chứng đều phải đúng.
  (1) Bảng đầu trang N là phần tiếp của bảng cuối trang N-1 (`continued_table`): kề sát qua trang (`adjacent_tables`, như lỗi 14), cùng số cột, và hoặc header giống header trang trước sau `normalise` (PDF in
  lại header, hoặc `carry_header` đã chép lên), hoặc TableFormer không gắn nhãn `column_header` cho ô nào của bảng (bảng chữ thuần mà lỗi 14 không tách được hàng đầu khỏi header: mục lục exhibit, danh sách công ty con).
  Bảng của kỳ khác đứng liền sau (Amazon 2017 p50-p51: bảng 2016 rồi bảng 2017, header khác ở chữ số, TableFormer thấy header) và bảng khác số cột không phải phần tiếp.
  (2) Tên bảng là tiêu đề cuối cùng nằm trên khối bảng cuối của trang N-1 (`table_heading`); bảng dài nhiều trang truyền tên qua chính dòng đã đặt ở trang trước. Không lấy "tiêu đề gần nhất trong tài liệu":
  nó gắn "SCHEDULE I NOTES TO SCHEDULE I" của p218 lên 31 trang danh sách công ty con của AES. Làm SAU `restore_titles` (lỗi 23), và chỉ khi dòng đầu có chữ của trang là hàng bảng, nên trang đã có tiêu đề hoặc
  đoạn dẫn riêng không đổi. Chữ "continued" là dấu hiệu `financial_chunker.stitcher.is_section_continuation` đã nhận, và tiêu đề đã có chữ này (PDF in sẵn) không bị gắn lần hai.
  Đo trên 84 tài liệu: 258 cặp trang là phần tiếp, 181 trang ở 50 tài liệu được đặt tên bảng, 74 cặp không có dòng tiêu đề nào nằm trên bảng ở trang trước (AES Exhibit 21: tên bảng "The AES Corporation 2022 Form 10-K
  Exhibit 21.1" chỉ là dòng chữ thường; và các danh sách exhibit khác) và 3 trang đã có chữ riêng nên không đổi; 99 cặp kề sát nhưng không phải phần tiếp (41 khác số cột, 58 header khác mà TableFormer thấy header).
  Mọi trang khác của 84 tài liệu giữ nguyên từng byte.

- Lỗi 16 (chỉ số chú thích in nhỏ bị tách thành cột "ma": JPM 2022 p136 bảng Total VaR 13 cột thay vì 7, 6 cột "(a)" "(e)" xen kẽ; Coca-Cola 2017 p47 một cột "3" "4" "5" mang tên nhóm "Percent Change - 2016 versus 2015",
  nên "Europe 1% | 3" đọc như Europe tăng 3%): PDF in chỉ số nhỏ hơn số (cao 0,5-0,85 lần, đa số 0,65), thường nâng lên, căn trái ở vị trí cố định cách số 0-20 điểm; TableFormer đặt chúng vào cột riêng và `regrid_block` (lỗi 12)
  còn tự tạo thêm cột như vậy từ khoảng ngang (JPM p136: cột cuối Docling để "NM (e)" trong một ô, regrid tách thành hai cột). Bằng chứng chỉ lấy từ PDF (`sits_on`): chữ cao không quá `SUPERSCRIPT_RATIO` lần chữ đứng trước và nâng lên
  ít nhất `SUPERSCRIPT_RAISE` điểm; riêng chỉ số chữ cái "(a)" còn nhận khi cùng đáy với số (JPM p128, p261). Hình dạng chữ không đủ: trên fixed/ trước khi sửa có 463 cột toàn chữ số 1-2 chữ số hoặc "(1)" ở 76 tài liệu, phần lớn là
  số liệu thật ("Age", "Page", số cửa hàng, mức "Level 1/2/3" của giá trị hợp lý, thời hạn năm), nên chỉ cột có bằng chứng cỡ chữ mới bị gộp. Hai chỗ sửa dùng chung bằng chứng đó:
  (1) trong `regrid_block`: `glue_superscripts` kéo mép phải của số ra hết chỉ số (chữ không đổi) nên chỉ số cùng cụm giá trị và cùng ô với số ("(43) (a)", "1% 3"); cột "ma" của lưới Docling (`ghost_columns`) không còn là nhãn lá
      (nhãn lá vẫn giữ khi ô header gộp bắt đầu ở cột ma và phủ cả cột số kề phải); còn cụm chỉ số thừa (chỉ số không đứng sau số, vd nhãn chữ) thì bỏ qua bảng (`regrid_skip_ghost`), để (2) xử lý.
  (2) bảng `regrid_block` không xử lý (bảng chữ, ô gộp trong thân, hàng xuống dòng) và bảng bị bỏ qua ở (1): `merge_ghost_columns` nối chữ cột "ma" vào ô kề trái trên Markdown, sau lỗi 3/11.
  Cột "ma" = mọi ô thân có chữ chỉ gồm chỉ số in nhỏ đứng sau một từ của ô kề trái (ô kề trái có chữ), header trống hoặc các thành phần của nó đã nằm liền nhau trong header MỘT cột khác. Giữ nguyên cột (không gộp) khi
  header là chính ký hiệu ("*" của Boeing 2018 p28: "737 *" và các số nhỏ "(18)" bên dưới là số giao nội bộ chứ không phải chú thích), là mảnh tên cột bị xé ("2021 - other income" của "All other income", JPM p191) hoặc tổ hợp chỉ có ở cột đó
  (JPM 2022Q2 p110 "2022 - Total changes ..."), vì gộp sẽ mất hoặc ghép sai tên cột. Đo trên 84 tài liệu (so với fixed/ trước đó): 232 bảng đổi ở 203 trang của 24 tài liệu, ít đi 365 cột (216 cột "ma" của lưới Docling, còn lại là cột regrid
  tự tạo), không đổi số dòng, số hàng bảng, không thêm chữ; chữ mất chỉ là header thừa ở 2 trang (Coca-Cola p47 "Percent Change - 2016 versus 2015", JPM 2022 p256 "Net liquidation losses / (recoveries)", cả hai còn nguyên trong tên cột kề).
  Cột chỉ số chữ cái 299 -> 13, ở 11 trang JPM (các ca nêu trên cùng JPM 2021Q1 p21: chỉ số nằm trên dòng khác với nhãn kề trái; JPM 2022Q2 p21 và p103: cột lệch header; JPM 2022 p242: cột lẫn số liệu của bảng khác).
- Lỗi 17 (đoạn chú thích cuối bảng bị nuốt làm một hàng của bảng, JPM p242 "(a) At December 31, 2022, $139 million of the $140 million total PPP loans ..." 711 chữ lặp qua 12 cột làm trang nặng 223 KB):
  TableFormer kéo hộp bao bảng trùm cả vùng chữ chú thích và coi nó là hàng dữ liệu gộp ngang. Bằng chứng là `docling.json` (hàng lưới có MỘT ô gộp phủ cả chiều ngang) cộng nội dung Markdown: đoạn
  chữ mở đầu bằng ký hiệu chú thích (`footnote_marker`: "(a)", "(1)", "*", "†", chữ số đơn) và ký hiệu đó có mặt ở một ô phía trên trong cùng bảng (chú thích của CHÍNH bảng này, không phải mục "(4) Instruments ..."
  của bảng mục lục exhibit). Hàng được lấy ra khỏi bảng thành một đoạn văn; hàng chú thích nằm giữa bảng thì bảng được chia đôi tại đó (GM p86: chú thích "(a)" của bảng Inventories nằm trước header của bảng
  Prepaid), nên chú thích đứng sát bảng của nó. Các bảng bị đụng được dựng lại với độ rộng cột theo ô dài nhất còn lại (không còn đệm theo đoạn chú thích). Làm SAU `carry_header` vì bước đó ghép khối bảng theo thứ tự.
  Hàng chú thích không phải ô gộp (chữ ở ô đầu, ô khác trống: Walmart 2018 p33 "(1) Through March 28, 2018.", JPM p61 "* Represents net income ...", 3M p45, GM 2019 p69) cũng được lấy ra khi ký hiệu có ở ô phía trên (từ riêng, hoặc "*" "†"
  dính cuối từ như "income*") VÀ hàng là hàng cuối bảng hoặc bảng là bảng số liệu; chữ ký "* By: /s/ ..." của Verizon (giữa bảng chữ) và mục lục AMCOR "(a) Financial Statements" (ký hiệu không có ở trên) giữ nguyên.
  Chữ thân bị nuốt vào bảng số liệu (Walmart 2018 p33: "Holders of Record of Common Stock", "As of March 28, 2018, there were ...", "Dividends Payable Per Share", "For fiscal 2019, dividends will be paid ...") cũng được lấy ra: bằng chứng là
  cỡ chữ PDF (chữ thân 8,8 pt so với 7,4 pt của bảng), không phải nội dung: hàng một chuỗi chữ, không đậm, từ PROSE_MIN_WORDS từ trở lên, sau một hàng có giá trị, cỡ chữ lớn hơn cỡ điển hình của bảng ít nhất PROSE_SIZE_MARGIN điểm là
  đoạn văn; hàng đậm đứng ngay trước đoạn văn như vậy là tiêu đề (cấp theo kiểu chữ như lỗi 5/23).

- Lỗi 23 (tiêu đề báo cáo tài chính chính bị mất, Verizon 2022 p54 "Consolidated Statements of Income" + "Verizon Communications Inc. and Subsidiaries"): Docling gán nhãn `page_header` cho dòng chữ
  sát mép trên trang nên `export_to_markdown` bỏ cả mục; bảng đứng một mình, không có tên báo cáo lẫn tên công ty. Bằng chứng là `docling.json` (nhãn, trang có bảng, hộp bao) cộng PDF (từng dòng chữ và
  kiểu chữ trong hộp bao mục). Chỉ khôi phục mục `page_header` thỏa đủ bốn điều: (1) có từ "statement(s)" hoặc "sheet(s)" (`TITLE_WORDS`); (2) chữ đó (bỏ chữ số) không in ở NAV_HEADER_MIN_PAGES trang
  trở lên của tài liệu dù Docling gán nhãn gì (header chạy "Notes to Consolidated Financial Statements" bị loại); (3) trang có bảng và mục nằm trên mọi phần tử khác của trang; (4) chữ từng dòng chưa có trên trang.
  Mỗi dòng chữ PDF của mục (Docling gộp tiêu đề với tên công ty làm một mục) được đặt lên đầu trang Markdown: dòng in đậm hoặc là tên Part/Item thành tiêu đề với cấp của kiểu chữ đó trong tài liệu (cùng
  bảng cấp của lỗi 5, kiểu chữ chưa có cấp thì lấy kiểu gần nhất), dòng không đậm là một dòng chữ thường. Làm SAU `fix_page` nên không đụng bước gỡ header điều hướng (lỗi 4).
- Lỗi 20 (thực thể HTML, Walmart 2019 p81 "Ernst &amp; Young LLP"): bộ ghi Markdown của Docling escape `&`, `<`, `>` thành `&amp;`, `&lt;`, `&gt;` (không PDF nào có chuỗi này thật), nên "S&P 500" thành
  "S&amp;P 500" trong chỉ mục BM25 và trong câu trả lời của LLM. Làm cuối cùng, ngay trước khi ghi trang (`unescape_markdown`), nên không đổi chữ mà các bước trước so khớp với PDF.
- Lỗi 19 (ô tick lỗi font, Walmart 2019 p2 "- [x] Yes ý" / "- [ ] No ¨"): PDF vẽ ô tick bằng font Wingdings, mã Latin "þ" và "ý" là ô đã tick, "¨" là ô trống, nên Docling xuất
  đúng chữ Latin đó (17 tài liệu, 192 ký tự; số ký tự mỗi trang trùng số ký tự Wingdings của PDF). Mỗi ký tự được đổi sang "☒" / "☐", chính ký hiệu Docling xuất ở các tài liệu có font đúng,
  chứ không xóa: "Yes ý No ¨" mà xóa thì không còn biết đã chọn Yes hay No. Mục danh sách Docling đã tự dựng "- [x]" / "- [ ]" mà chỉ còn MỘT ô cùng trạng thái ở đầu hoặc cuối
  thì ô đó thừa và bị bỏ ("- [x] Yes ý" thành "- [x] Yes"). Làm sau `unescape_markdown` như lỗi 20 vì các bước trước so ô bảng với chữ PDF, trong đó ô tick vẫn là "þ" / "¨".
  Chưa xử lý: Wingdings "o" (ô trống) và "x" (ô tick) giống chữ thường nên chỉ phân biệt được bằng vị trí trong PDF.

Dùng: python docling_raw/postprocess.py [DOC ...]   (mặc định mọi tài liệu trong docling_raw/output)
Đầu ra: docling_raw/fixed/<DOC>/{full.md, pages/page_NNN.md, fix_report.json}; full.md = các trang đã sửa nối bằng một dòng trắng.
"""

from app.services.ingestion.postprocess.run import process

__all__ = ["process"]
