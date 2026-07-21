"""
Static knowledge documents for the RAG system.
Loaded once at startup; searched by the retrieve_knowledge tool.
"""

from langchain_core.documents import Document

STATIC_DOCS = [
    Document(
        page_content="""
Quy trình tổ chức buổi đánh cầu lông (Admin Workflow):

Bước 1 - Tạo ngày đánh: Admin tạo buổi đánh mới với tên đầy đủ (ví dụ: "15h-17h Thứ 7 ngày 27/6, sân Kim Châu"), số suất nam/nữ nếu muốn giới hạn (ví dụ "5 nam, 3 nữ"), và chọn có mở đăng ký ngay không.

Bước 2 - Mở đăng ký: Admin chọn ngày đánh (is_selected=true) để thành viên đăng ký tham gia qua app. Chỉ một ngày được mở cùng lúc — khi chọn ngày mới, ngày cũ tự động bị đóng.

Bước 3 - Quản lý người tham gia: Admin thêm hoặc xóa người chơi. Mỗi người có tên, trình độ (mới/trung bình/khá/cao), giới tính (nam/nữ) và trạng thái (tham gia/vắng).

Bước 4 - Tính tiền: Sau buổi đánh, admin nhập chi phí thực tế theo dạng văn bản tự nhiên. Hệ thống tự tính số tiền mỗi người cần đóng. Sau bước này ngày bị khóa — không thêm/xóa người được nữa.

Bước 5 - Công bố kết quả: Admin đăng ảnh QR chuyển khoản và bật hiển thị kết quả để tất cả thành viên xem số tiền và quét QR thanh toán.
        """.strip(),
        metadata={"source": "huong-dan-admin", "topic": "workflow"},
    ),
    Document(
        page_content="""
Cách nhập chi phí để tính tiền buổi đánh:

Hệ thống tính tiền dựa trên văn bản chi phí do admin nhập. Admin phải nhập CHÍNH XÁC, không viết tắt hoặc đổi tên người.

Ví dụ cú pháp hợp lệ:
- "sân 160k, cầu 100k" → Tổng 260k chia đều cho tất cả người tham gia
- "sân 200k, cầu 50k, Lan trả sân" → Lan trả 200k tiền sân, 50k còn lại chia đều
- "sân 300k, cầu 80k, Minh và Nam trả hết" → Minh + Nam chịu toàn bộ 380k, người khác miễn phí
- "sân 150k, cầu 60k, chia đều" → Tổng 210k chia đều
- "sân 160k, cầu 100k, Ni trả hết" → Ni trả toàn bộ 260k

Sau khi tính tiền:
- Mỗi người có số tiền hiển thị cụ thể
- Ngày bị khóa hoàn toàn (isCalculated=true)
- Admin mới có thể show kết quả

Lỗi thường gặp:
- Sai tên người trong phần chi phí → tính toán sai
- Nhập sau khi đã tính tiền → bị chặn (lỗi 400)
        """.strip(),
        metadata={"source": "tinh-tien", "topic": "payment"},
    ),
    Document(
        page_content="""
Quản lý suất tham gia (Slot Management):

Mỗi ngày đánh có thể giới hạn số suất nam và nữ. Thông tin nhập ở phần "nội dung" khi tạo ngày.

Ví dụ: "5 nam, 3 nữ" → tối đa 5 người nam và 3 người nữ.

Các chỉ số:
- male_total / female_total: Tổng suất mỗi giới
- male_remain / female_remain: Suất còn trống
- Khi remain = 0: Không thể thêm người giới tính đó (lỗi 400)

Nếu không đặt giới hạn (total = 0): Không giới hạn số người.

Khi thêm người: suất tự giảm. Khi xóa người: suất được hoàn lại tự động.

Nếu thêm người mà không còn suất: hệ thống báo lỗi "hết suất", admin cần xóa người khác trước hoặc tăng giới hạn bằng cách sửa ngày đánh.
        """.strip(),
        metadata={"source": "quan-ly-suat", "topic": "slots"},
    ),
    Document(
        page_content="""
Ý nghĩa các trạng thái của ngày đánh:

is_selected = true (Đang mở đăng ký):
- Thành viên đăng ký được qua app người dùng
- Chỉ một ngày được chọn cùng lúc
- Admin vẫn thêm/xóa người thủ công được

is_selected = false (Đã đóng đăng ký):
- Thành viên không đăng ký qua app được nữa
- Admin vẫn thêm/xóa người thủ công (nếu chưa tính tiền)

isCalculated = true (Đã tính tiền):
- Chi phí đã được chia, mỗi người có số tiền cụ thể
- KHÔNG thể thêm hoặc xóa người
- KHÔNG thể xóa ngày đánh này
- Chỉ có thể show kết quả

isShowMoney = true (Đã công bố kết quả):
- Tất cả thành viên đã thấy số tiền trong app
- QR chuyển khoản đã được đăng kèm
        """.strip(),
        metadata={"source": "trang-thai-ngay", "topic": "status"},
    ),
    Document(
        page_content="""
FAQ - Câu hỏi thường gặp khi quản lý buổi đánh:

H: Làm sao thêm người vào ngày đánh?
Đ: Nói với agent: "Thêm [tên] vào ngày [tên ngày], giới tính [nam/nữ], trình độ [trình độ]". Agent xác nhận trước khi thực hiện.

H: Tại sao không xóa được người chơi?
Đ: Ngày đã tính tiền (isCalculated=true) thì không thể xóa người. Kiểm tra bằng "liệt kê các ngày đánh".

H: Làm sao mở ngày đánh cho thành viên đăng ký?
Đ: Yêu cầu "chọn ngày [tên] để mở đăng ký". Chỉ một ngày được mở cùng lúc — ngày trước tự đóng.

H: Cách xem danh sách người đã đăng ký?
Đ: Yêu cầu "xem danh sách người tham gia ngày [tên ngày]".

H: Tại sao tạo ngày mới bị lỗi?
Đ: Tên ngày trùng với ngày đã có, hoặc thiếu thông tin bắt buộc.

H: Làm sao biết ai chưa trả tiền?
Đ: Xem danh sách người tham gia — trường isPaid=false là chưa trả.

H: Có thể xóa ngày đã tính tiền không?
Đ: Không. Ngày isCalculated=true bị khóa hoàn toàn, không xóa được.

H: Show kết quả nhưng chưa có QR thì sao?
Đ: Phải cung cấp URL ảnh QR mới show được. Nếu chưa có QR, cần upload ảnh lên trước rồi lấy URL.
        """.strip(),
        metadata={"source": "faq", "topic": "faq"},
    ),
    Document(
        page_content="""
Hướng dẫn show kết quả và QR thanh toán:

Điều kiện: ngày đánh phải có isCalculated=true (đã tính tiền xong).

Các bước:
1. Chuẩn bị ảnh QR code ngân hàng (Vietcombank, MB Bank, VPBank, v.v.)
2. Upload ảnh lên hosting hoặc lấy URL từ dịch vụ lưu trữ ảnh
3. Yêu cầu agent: "Show kết quả ngày [tên], QR: [URL ảnh]"

Kết quả thành viên thấy:
- Danh sách tên + số tiền mỗi người cần đóng
- Ảnh QR để quét chuyển khoản

Lỗi thường gặp:
- "Chưa tính tiền" → Phải chạy tính tiền trước
- "Thiếu QR" → URL ảnh không hợp lệ hoặc chưa cung cấp
- URL ảnh phải là link trực tiếp đến file ảnh (kết thúc bằng .jpg/.png hoặc link CDN)
        """.strip(),
        metadata={"source": "show-ket-qua", "topic": "payment"},
    ),
    Document(
        page_content="""
Quy định và lưu ý chung của hệ thống:

Tên ngày đánh: Phải rõ ràng, đầy đủ thông tin thời gian và địa điểm. Không đặt trùng tên. Ví dụ chuẩn: "15h-17h Thứ 7 27/06/2025, sân Kim Châu".

Trình độ người chơi: mới / trung bình / khá / cao. Để trống nếu không rõ.

Giới tính: nam / nữ (hoặc male / female — hệ thống tự nhận).

Xác nhận trước khi thực hiện: Các thao tác quan trọng (tạo ngày, xóa, tính tiền, show kết quả) đều yêu cầu xác nhận của admin trước khi thực hiện.

Không thể hoàn tác: Xóa ngày, xóa người, và tính tiền là các thao tác không thể hoàn tác. Kiểm tra kỹ trước khi xác nhận.

Một admin — một cuộc hội thoại: Mỗi tài khoản admin có một lịch sử trò chuyện riêng, được lưu trên server. Dùng "bắt đầu cuộc trò chuyện mới" để xóa lịch sử khi cần.
        """.strip(),
        metadata={"source": "quy-dinh-chung", "topic": "rules"},
    ),
]
