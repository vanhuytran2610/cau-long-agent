"""
LangGraph agent for badminton-day admin tasks.

Tools wrap the existing Express routes (via ExpressClient). The model picks
tools from their descriptions. Write actions (calculate / export / edit) are
gated behind an in-chat confirmation enforced by the system prompt.
"""

import json
import os
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from express_client import ExpressClient
from prompts import get_system_prompt

XAI_MODEL = os.environ.get("XAI_MODEL", "grok-4.3")


def json_response(data, message: str = "", status_code: int = 200) -> str:
    return json.dumps(
        {"status_code": status_code, "message": message, "data": data},
        ensure_ascii=False,
    )


def build_tools(client: ExpressClient):
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

    return [
        list_categories,
        list_participants,
        create_vote_date,
        calculate,
        show_result,
        edit_date,
        add_participant,
        delete_participant,
        delete_date,
    ]


def build_agent(jwt: str, checkpointer, language: str = "vi"):
    """One agent per request, bound to the calling admin's JWT."""
    client = ExpressClient(jwt)
    llm = ChatOpenAI(
        model=XAI_MODEL,
        api_key=os.environ["XAI_API_KEY"],
        base_url="https://api.x.ai/v1",
        temperature=0,
    )
    tools = build_tools(client)
    return create_react_agent(
        llm, tools, checkpointer=checkpointer, prompt=get_system_prompt(language)
    )
