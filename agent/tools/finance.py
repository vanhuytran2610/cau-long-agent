from langchain_core.tools import tool

from agent.tools import json_response


def build_finance_tools(client):
    @tool
    async def calculate(category_id: str, payment_info: str) -> str:
        """Tính chi phí buổi đánh, chia tiền từng người, lưu kết quả vào hệ thống.
        Sau khi gọi, ngày sẽ có isCalculated=true — không thể thêm/xóa người chơi nữa.

        Args:
            category_id: ID lấy từ list_categories.
            payment_info: COPY NGUYÊN VĂN từng chữ từ tin nhắn admin.
                          KHÔNG sửa, KHÔNG paraphrase, KHÔNG tóm tắt, KHÔNG dịch.
                          Sai một chữ tiếng Việt → tính toán sai.
                          Ví dụ: admin nói "sân 160k, cầu 100k, Ni trả hết"
                          → payment_info = "sân 160k, cầu 100k, Ni trả hết"

        Bị chặn nếu chưa có người tham gia với status "tham gia".
        Yêu cầu xác nhận trước khi gọi.
        Kích hoạt khi admin nói: "tính tiền ngày...", "chia tiền buổi...", "ai trả bao nhiêu".
        """
        res = await client.calculate(category_id, payment_info)
        data = res.get("data") or {}
        exp = data.get("expenses") or {}
        if exp:
            return json_response(
                exp, message="Đã tính tiền xong.\n" + (exp.get("payment_text") or "")
            )
        return json_response(
            None,
            message=f'Không tính được: {res.get("message") or res}',
            status_code=400,
        )

    @tool
    async def show_result(category_id: str, qr_img_url: str) -> str:
        """Bật hiển thị kết quả thanh toán cho tất cả user xem (isShowMoney=true).
        Đính kèm ảnh QR chuyển khoản để user quét thanh toán.

        Args:
            category_id: ID lấy từ list_categories.
            qr_img_url: URL ảnh QR chuyển khoản. Nếu admin chưa cung cấp: HỎI LẠI, không tự bịa.

        Bị chặn (lỗi 400) nếu ngày chưa tính tiền (isCalculated=false).
        Nếu chưa tính tiền: báo admin phải chạy calculate trước.

        Yêu cầu xác nhận trước khi gọi.
        Kích hoạt khi admin nói: "show kết quả ngày...", "cho mọi người xem tiền",
        "mở kết quả", "publish kết quả".
        """
        res = await client.export_result(category_id, qr_img_url=qr_img_url)
        if res.get("_status") == 200:
            return json_response(None, message="Đã bật hiển thị kết quả cho user.")
        return json_response(
            None,
            message=f'Không show được: {res.get("message") or res}',
            status_code=400,
        )

    return [calculate, show_result]
