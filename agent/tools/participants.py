from langchain_core.tools import tool

from agent.tools import json_response


def build_participant_tools(client):
    @tool
    async def list_participants(category_id: str) -> str:
        """Liệt kê tất cả người tham gia của một ngày đánh.

        Trả về participant_id — BẮT BUỘC dùng để gọi delete_participant.
        KHÔNG tự đoán participant_id từ tên người chơi.

        Prerequisite: gọi list_categories trước để lấy category_id.
        Kích hoạt khi admin nói: "ngày X có ai đăng ký", "xem người tham gia",
        "ai chưa trả tiền", "danh sách buổi...".
        """
        res = await client.list_participants(category_id)
        data = res.get("data") or {}
        parts = data.get("participants", [])
        if not parts:
            return json_response(
                [], message="Ngày này chưa có ai đăng ký tham gia.", status_code=404
            )
        lines = [
            f"- [internal_id:{p.get('_id')}] {p.get('name')} | {p.get('status')} | "
            f"giới tính: {p.get('gender') or '?'} | "
            f"tiền: {p.get('money')} | đã trả: {p.get('isPaid')}"
            for p in parts
        ]
        return json_response(lines, message=f"Có {len(parts)} người tham gia.")

    @tool
    async def add_participant(
        category_id: str, name: str, level: str, gender: str
    ) -> str:
        """Thêm một người chơi vào ngày đánh với trạng thái "tham gia".

        Args:
            category_id: ID lấy từ list_categories.
            name: Tên người chơi, giữ nguyên cách viết của admin. Tên trùng trong cùng ngày sẽ bị lỗi.
            level: Trình độ. Ví dụ: "mới", "trung bình", "khá", "cao". Để "" nếu không rõ.
            gender: "nam" hoặc "nữ". Chấp nhận cả "male"/"female".
                    Hỏi lại nếu admin chưa nói rõ.
                    Nếu ngày có giới hạn suất (male_total/female_total > 0):
                    sẽ bị lỗi 400 khi hết suất của giới tính đó.

        Bị chặn (lỗi 400) nếu ngày đã tính tiền (isCalculated=true).
        Kích hoạt khi admin nói: "thêm người...", "add... vào ngày...", "đăng ký cho...".
        """
        res = await client.add_participant(category_id, name, level, gender)
        if res.get("_status") == 201:
            return json_response(
                {"name": name}, message=f'Đã thêm "{name}" vào ngày.', status_code=201
            )
        return json_response(
            None,
            message=f'Không thêm được: {res.get("message") or res}',
            status_code=400,
        )

    @tool
    async def delete_participant(category_id: str, participant_id: str) -> str:
        """Xóa một người chơi khỏi ngày đánh. Tự động hoàn trả suất về slot.

        Args:
            category_id: ID lấy từ list_categories.
            participant_id: ID người chơi — lấy từ kết quả list_participants (trường id=...).
                            KHÔNG tự đoán ID — phải gọi list_participants trước.

        Bị chặn (lỗi 400) nếu ngày đã tính tiền (isCalculated=true).
        Yêu cầu xác nhận trước khi gọi.
        Kích hoạt khi admin nói: "xóa... khỏi ngày...", "bỏ người...", "remove...".
        """
        res = await client.delete_participant(category_id, participant_id)
        if res.get("_status") == 200:
            return json_response(None, message="Đã xóa người chơi khỏi ngày.")
        return json_response(
            None,
            message=f'Không xóa được: {res.get("message") or res}',
            status_code=400,
        )

    return [list_participants, add_participant, delete_participant]
