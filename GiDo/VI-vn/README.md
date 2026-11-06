<p align="center"><img src="banner.svg" alt="FODB" width="100%"></p>

<p align="center">
<a href="../../README.md"><img src="../../docs/lang/EN-en-off.svg" height="26" alt="English"></a>
<a href="../../GiDo/RU-ru/README.md"><img src="../../docs/lang/RU-ru-off.svg" height="26" alt="Русский"></a>
<a href="../../GiDo/ZH-cn/README.md"><img src="../../docs/lang/ZH-cn-off.svg" height="26" alt="简体中文"></a>
<a href="../../GiDo/ES-es/README.md"><img src="../../docs/lang/ES-es-off.svg" height="26" alt="Español"></a>
<a href="../../GiDo/HI-in/README.md"><img src="../../docs/lang/HI-in-off.svg" height="26" alt="हिन्दी"></a>
<a href="../../GiDo/FR-fr/README.md"><img src="../../docs/lang/FR-fr-off.svg" height="26" alt="Français"></a>
<a href="../../GiDo/BN-bd/README.md"><img src="../../docs/lang/BN-bd-off.svg" height="26" alt="বাংলা"></a>
<a href="../../GiDo/PT-br/README.md"><img src="../../docs/lang/PT-br-off.svg" height="26" alt="Português"></a>
<a href="../../GiDo/UR-pk/README.md"><img src="../../docs/lang/UR-pk-off.svg" height="26" alt="اردو"></a>
<a href="../../GiDo/ID-id/README.md"><img src="../../docs/lang/ID-id-off.svg" height="26" alt="Indonesia"></a>
<a href="../../GiDo/DE-de/README.md"><img src="../../docs/lang/DE-de-off.svg" height="26" alt="Deutsch"></a>
<a href="../../GiDo/JA-jp/README.md"><img src="../../docs/lang/JA-jp-off.svg" height="26" alt="日本語"></a>
<a href="../../GiDo/TR-tr/README.md"><img src="../../docs/lang/TR-tr-off.svg" height="26" alt="Türkçe"></a>
<a href="../../GiDo/KO-kr/README.md"><img src="../../docs/lang/KO-kr-off.svg" height="26" alt="한국어"></a>
<a href="../../GiDo/VI-vn/README.md"><img src="../../docs/lang/VI-vn-on.svg" height="26" alt="Tiếng Việt"></a>
<a href="../../GiDo/IT-it/README.md"><img src="../../docs/lang/IT-it-off.svg" height="26" alt="Italiano"></a>
<a href="../../GiDo/PL-pl/README.md"><img src="../../docs/lang/PL-pl-off.svg" height="26" alt="Polski"></a>
<a href="../../GiDo/UK-ua/README.md"><img src="../../docs/lang/UK-ua-off.svg" height="26" alt="Українська"></a>
<a href="../../GiDo/TH-th/README.md"><img src="../../docs/lang/TH-th-off.svg" height="26" alt="ไทย"></a>
</p>

<p align="center"><a href="https://github.com/Arkomiko/Fruity-Organizer-DataBase/releases/latest"><b>⬇ Tải FODB.exe</b></a></p>

Công cụ sắp xếp di động cho cơ sở dữ liệu plugin của FL Studio. Sắp plugin vào thư mục theo hãng, theo công dụng hoặc cả hai, với giao diện hòa hợp cùng FL Studio.

<p align="center"><img src="../../docs/demo-en.gif" alt="FODB" width="100%"></p>

## Tính năng

- Sắp theo hãng, theo công dụng hoặc lồng theo thứ tự bất kỳ: Hãng\Công dụng hoặc Công dụng\Hãng
- Xác định công dụng của từng plugin: reverb, EQ, dynamics, synth và 18 loại khác
- Lọc theo công dụng, hãng, định dạng, bit, trạng thái, ngày tệp, kích thước và hơn thế
- Theo dõi giao diện FL Studio hiện tại theo thời gian thực
- Sao lưu tự động, hoàn tác một lần nhấp, không có gì ra ngoài thư mục cơ sở dữ liệu
- Một tệp 9 MB không cần cài đặt; thiết lập nằm ngay bên cạnh
- 19 ngôn ngữ giao diện cùng cài đặt bố cục, phím tắt, tỷ lệ, phông chữ, màu sắc và hơn thế

## Bắt đầu nhanh

1. Tải FODB.exe và chạy. Cơ sở dữ liệu plugin được tìm tự động.
2. Chọn bố cục thư mục, rồi bật hoặc tắt nguồn và bộ lọc.
3. Nhấn “Sắp xếp plugin”, kiểm tra bản xem trước, rồi làm mới trình duyệt plugin trong FL Studio.

## Bố cục thư mục

<p align="center"><img src="workflow.svg" alt="Bố cục thư mục" width="100%"></p>

Chọn mẫu có sẵn hoặc tự viết mẫu từ các phần sau:

```text
{vendor}  {purpose}  {format}  {bits}  {letter}  {kind}

{vendor}\{purpose}
{purpose}\{vendor}
USER\{format}\{vendor}
```

## Bộ lọc

Đánh dấu giá trị trong menu Bộ lọc hoặc nhập điều kiện vào ô tìm kiếm:

```text
purpose:reverb,delay                 reverb OR delay
vendor:"plugin alliance" -format:vst  one vendor, without VST2
organized:no kind:synth               synths not organized yet
age:30d bits:64                       64-bit, dated in the last 30 days
```

## Giao diện FL Studio

<p align="center"><img src="themes.svg" alt="Giao diện FL Studio" width="100%"></p>

FODB đọc giao diện đang dùng và cập nhật màu khi bạn đổi trong FL Studio. Màu nền rất gần nhưng không giống hệt đến từng điểm ảnh.

## An toàn

- Plugin của bạn không bao giờ bị thay đổi. Trong thư mục Installed chỉ danh sách New có thể đổi: plugin đã sắp xếp sẽ rời danh sách, và có thể tắt việc này.
- Mọi lần chạy đều hoàn tác được, tệp bị xóa sẽ vào Thùng rác.
- Trước mỗi thay đổi, một bản sao lưu ZIP của cơ sở dữ liệu được tạo; giữ 40 bản mới nhất và có thể đổi số lượng.

## Quy tắc riêng

Thêm quy tắc trong thẻ Cài đặt hoặc FODB.json để đặt công dụng theo tên hay nhà sản xuất bằng biểu thức chính quy:

```json
"purpose_rules": [
  { "purpose": "drums", "name": "kick|808" },
  { "purpose": "vocal", "vendor": "antares" }
]
```

## Dựng từ mã nguồn

Cần Windows và Python 3.13. Chương trình chỉ dùng thư viện chuẩn.

```powershell
./build.ps1
```

## Ghi công

Dựa trên FL Studio Automatic Plugin Organizer của Magabes và các cộng tác viên, theo giấy phép MIT.

Dự án độc lập, không liên kết với Image-Line. FL Studio là thương hiệu của Image-Line.
