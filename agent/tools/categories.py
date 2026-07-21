from langchain_core.tools import tool

from agent.tools import json_response


def build_category_tools(client):
    @tool
    async def list_categories() -> str:
        """Liệt kê tất cả ngày đánh cầu lông, sắp xếp MỚI NHẤT trước.

        PHẢI gọi công cụ này trước mọi thao tác cần category_id.
        Dùng kết quả để xác định trạng thái ngày trước khi hành động:
          - is_selected=true  → ngày đang mở cho user vote/đăng ký
          - isCalculated=true → đã tính tiền (chặn: add/delete người, delete ngày)
          - isShowMoney=true  → kết quả đã hiển thị cho user

        Khi trả lời admin: CHỈ hiển thị tên ngày, KHÔNG hiển thị id.
        Kích hoạt khi admin nói: "có những ngày nào", "ngày gần nhất",
        "liệt kê buổi đánh", "ngày nào đang mở vote".
        """
        res = await client.list_categories()
        cats = res.get("data") or []
        if not cats:
            return json_response([], message="Chưa có ngày đánh nào.")
        lines = []
        for i, c in enumerate(cats):
            qty = c.get("quantity") or {}
            label = " ⭐(mới nhất)" if i == 0 else ""
            flags = []
            if c.get("is_selected"):
                flags.append("đang vote")
            if c.get("isCalculated"):
                flags.append("đã tính tiền")
            if c.get("isShowMoney"):
                flags.append("đã show kết quả")
            flag_str = f" [{', '.join(flags)}]" if flags else ""
            slot_str = ""
            if qty.get("male_total") or qty.get("female_total"):
                slot_str = f" | suất: nam {qty.get('male_remain',0)}/{qty.get('male_total',0)}, nữ {qty.get('female_remain',0)}/{qty.get('female_total',0)}"
            lines.append(
                f"- [internal_id:{c.get('_id')}] {c.get('name')}{label}{flag_str}{slot_str}"
            )
        return json_response(lines, message=f"Đã liệt kê {len(cats)} ngày đánh.")

    @tool
    async def create_vote_date(name: str, content: str, is_selected: bool) -> str:
        """Tạo một ngày đánh cầu lông mới.

        Args:
            name: Tên do admin nói rõ ràng, ví dụ "15h-17h Thứ 7 ngày 27/6, sân Kim Châu".
                  KHÔNG tự đặt tên nếu admin chưa nói — hỏi lại ngay.
                  Tên trùng với ngày đã có sẽ bị lỗi 400.
            content: Mô tả số suất để tracking slot, ví dụ "5 nam, 3 nữ".
                     Để "" nếu admin không đề cập số suất.
            is_selected: True nếu admin muốn mở ngày này cho user vote/đăng ký ngay.
                         Mặc định Không (False).

        Yêu cầu xác nhận trước khi gọi.
        Kích hoạt khi admin nói: "tạo ngày...", "mở buổi đánh...", "thêm ngày mới...".
        """
        res = await client.create_category(name, content, is_selected)
        if res.get("_status") == 201:
            return json_response(
                {"name": name}, message=f'Đã tạo ngày "{name}".', status_code=201
            )
        return json_response(
            None,
            message=f'Không tạo được: {res.get("message") or res}',
            status_code=400,
        )

    @tool
    async def edit_date(
        category_id: str, name: str, content: str, is_selected: bool
    ) -> str:
        """Sửa thông tin một ngày đánh: tên, nội dung, và/hoặc trạng thái vote.

        Args:
            category_id: ID lấy từ list_categories.
            name: Tên mới. Nếu không đổi tên, truyền tên hiện tại.
            content: Nội dung mới (mô tả số suất).
                     Nếu không đổi content, truyền nội dung hiện tại.
                     Truyền "" để xóa nội dung.
            is_selected: REQUIRED — PHẢI LUÔN TRUYỀN, không được bỏ trống.
                         True = chọn ngày này để mở vote (tự bỏ chọn tất cả ngày khác).
                         False = bỏ chọn ngày này (user không thể đăng ký nữa).

        Prerequisite: gọi list_categories trước để lấy category_id, tên và nội dung hiện tại.
        Yêu cầu xác nhận trước khi gọi.
        Kích hoạt khi admin nói: "đổi tên ngày...", "chọn ngày... để vote", "đóng đăng ký ngày...".
        """
        res = await client.edit_category(category_id, name, content, is_selected)
        if res.get("_status") == 200:
            return json_response(
                {"name": name, "is_selected": is_selected},
                message=f'Đã cập nhật ngày "{name}" thành công.',
            )
        return json_response(
            None,
            message=f'Không sửa được: {res.get("message") or res}',
            status_code=400,
        )

    @tool
    async def delete_date(category_id: str) -> str:
        """Xóa vĩnh viễn một ngày đánh cùng toàn bộ người tham gia của ngày đó.

        Không thể hoàn tác.
        Bị chặn (lỗi 400) nếu ngày đã tính tiền (isCalculated=true).
        Kiểm tra isCalculated trong kết quả list_categories trước khi gọi.

        Prerequisite: gọi list_categories trước để lấy category_id và xác nhận isCalculated=false.
        Yêu cầu xác nhận trước khi gọi.
        Kích hoạt khi admin nói: "xóa ngày...", "hủy buổi...", "bỏ ngày...".
        """
        res = await client.delete_category(category_id)
        if res.get("_status") == 200:
            return json_response(
                None, message="Đã xóa ngày và toàn bộ người tham gia thành công."
            )
        return json_response(
            None,
            message=f'Không xóa được: {res.get("message") or res}',
            status_code=400,
        )

    return [list_categories, create_vote_date, edit_date, delete_date]
