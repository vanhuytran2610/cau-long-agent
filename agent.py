"""
LangGraph agent for badminton-day admin tasks.

Tools wrap the existing Express routes (via ExpressClient). The model picks
tools from their Vietnamese descriptions. Write actions (calculate / export /
edit) are gated behind an in-chat confirmation enforced by the system prompt.
"""

import os
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from express_client import ExpressClient

XAI_MODEL = os.environ.get("XAI_MODEL", "grok-4.3")

SYSTEM_PROMPT = """Bạn là trợ lý quản lý ngày đánh cầu lông cho admin.
Bạn có các công cụ để: tạo ngày đánh, xem danh sách ngày/người tham gia,
tính tiền, show kết quả cho user, và sửa ngày đánh.

QUY TẮC BẮT BUỘC:
1. Luôn trả lời bằng tiếng Việt, ngắn gọn, thân thiện.
   TUYỆT ĐỐI không nhắc đến tên công cụ/hàm nội bộ (list_categories, create_vote_date, calculate, v.v.) trong câu trả lời.
   Thay vào đó dùng ngôn ngữ tự nhiên, ví dụ: "Tôi sẽ xem danh sách ngày đánh cho bạn" thay vì "tôi sẽ gọi list_categories".
2. Trước khi TÍNH TIỀN / SỬA / SHOW KẾT QUẢ cho một ngày: phải gọi
   list_categories để tìm đúng category_id. Nếu có nhiều ngày tên giống nhau,
   hỏi admin chọn cái nào — KHÔNG tự đoán.
3. Khi gọi công cụ tính tiền: tham số payment_info PHẢI là bản copy nguyên văn từ tin nhắn admin, KHÔNG được tự sửa chữ, thêm bớt, hay diễn đạt lại — vì sửa chữ tiếng Việt gây lỗi font.
4. Nếu thiếu thông tin để gọi công cụ:
   - TẠO NGÀY (create_vote_date): tên ngày PHẢI do admin nói rõ ràng (ví dụ "15h-17h Thứ 7 ngày 27/6, sân Kim Châu").
     Nếu admin chỉ nói "tạo ngày" hoặc "tạo ngày mới" mà CHƯA có tên/ngày giờ cụ thể:
     HỎI LẠI ngay, ví dụ "Bạn muốn đặt tên ngày là gì?"
     TUYỆT ĐỐI không tự đặt tên, không dùng câu hỏi hay mô tả làm tên ngày.
   - Các thông tin khác (payment_info, category_id...): HỎI LẠI admin, TUYỆT ĐỐI không tự bịa.
5. XÁC NHẬN trong chat trước khi thực hiện hành động ghi dữ liệu
   (calculate, show_result, edit_date). Tóm tắt việc sắp làm và hỏi
   "Bạn xác nhận chứ?" rồi chỉ gọi công cụ khi admin đồng ý ở lượt sau.
6. Hành động chỉ ĐỌC (list_categories, list_participants) thì chạy thẳng,
   không cần xác nhận.
"""


def build_tools(client: ExpressClient):
    @tool
    async def list_categories() -> str:
        """Liệt kê tất cả ngày đánh hiện có. Danh sách sắp xếp MỚI NHẤT trước (index 0 = ngày gần nhất).
        Dùng để lấy category_id trước khi gọi các công cụ khác.
        Khi trả lời admin, chỉ hiển thị tên ngày — KHÔNG hiển thị id.
        Admin thường nói: "có những ngày nào", "ngày gần nhất", "liệt kê các buổi đánh"."""
        res = await client.list_categories()
        cats = res.get("data") or []
        if not cats:
            return "Chưa có ngày đánh nào."
        lines = []
        for i, c in enumerate(cats):
            label = " (mới nhất)" if i == 0 else ""
            lines.append(f"- id={c.get('_id')} | {c.get('name')}{label}")
        return "\n".join(lines)

    @tool
    async def list_participants(category_id: str) -> str:
        """Xem danh sách người đăng ký tham gia một ngày đánh.
        Admin thường nói: "ngày X ai đăng ký rồi", "xem người tham gia"."""
        res = await client.list_participants(category_id)
        data = res.get("data") or {}
        parts = data.get("participants", [])
        if not parts:
            return "Ngày này chưa có ai đăng ký tham gia."
        return "\n".join(f"- {p.get('name')} ({p.get('status')}) "
                         f"tiền: {p.get('money')} | đã trả: {p.get('isPaid')}"
                         for p in parts)

    @tool
    async def create_vote_date(name: str) -> str:
        """Tạo một ngày đánh cầu lông mới (category).
        name: mô tả ngày, ví dụ "15h-17h, Thứ 7 ngày 13/6, sân Kim Châu".
        Admin thường nói: "tạo ngày...", "mở buổi đánh...", "thêm ngày 20/6"."""
        res = await client.create_category(name)
        if res.get("_status") == 201:
            return f'Đã tạo ngày "{name}".'
        return f'Không tạo được: {res.get("message") or res}'

    @tool
    async def calculate(category_id: str, payment_info: str) -> str:
        """Tính tiền cho một ngày đánh và cập nhật số tiền từng người.
        Chỉ gọi sau khi admin đã xác nhận.
        payment_info: COPY NGUYÊN VĂN đúng từng chữ từ tin nhắn của admin, KHÔNG paraphrase, KHÔNG sửa chữ, KHÔNG tóm tắt lại.
        Ví dụ nếu admin nói "tiền sân 160k, tiền cầu 100k, Ni trả hết, mọi người chuyển cho Ni"
        thì payment_info = "tiền sân 160k, tiền cầu 100k, Ni trả hết, mọi người chuyển cho Ni".
        Admin thường nói: "tính tiền ngày...", "chia tiền buổi..."."""
        res = await client.calculate(category_id, payment_info)
        data = res.get("data") or {}
        exp = data.get("expenses") or {}
        if exp:
            return ("Đã tính tiền xong.\n" + (exp.get("payment_text") or ""))
        return f'Không tính được: {res.get("message") or res}'

    @tool
    async def show_result(category_id: str, qr_img_url: str) -> str:
        """Bật hiển thị kết quả tiền cho user xem (isShowMoney=true).
        Yêu cầu ngày đã được tính tiền và có ảnh QR. Chỉ gọi sau khi admin xác nhận.
        qr_img_url: link ảnh QR chuyển khoản.
        Admin thường nói: "show kết quả ngày...", "cho mọi người xem tiền"."""
        res = await client.export_result(category_id, qr_img_url=qr_img_url)
        if res.get("_status") == 200:
            return "Đã bật hiển thị kết quả cho user."
        return f'Không show được: {res.get("message") or res}'

    @tool
    async def edit_date(category_id: str, name: str, is_selected: bool) -> str:
        """Sửa tên ngày đánh và/hoặc đặt nó làm ngày đang được chọn để vote.
        is_selected=true sẽ bỏ chọn tất cả ngày khác. Chỉ gọi sau khi admin xác nhận.
        Admin thường nói: "đổi tên ngày...", "chọn ngày... để vote"."""
        res = await client.edit_category(category_id, name, is_selected)
        if res.get("_status") == 200:
            return f'Đã cập nhật ngày thành "{name}" (đang chọn: {is_selected}).'
        return f'Không sửa được: {res.get("message") or res}'

    return [list_categories, list_participants, create_vote_date,
            calculate, show_result, edit_date]


def build_agent(jwt: str, checkpointer):
    """One agent per request, bound to the calling admin's JWT."""
    client = ExpressClient(jwt)
    llm = ChatOpenAI(
        model=XAI_MODEL,
        api_key=os.environ["XAI_API_KEY"],
        base_url="https://api.x.ai/v1",
        temperature=0,
    )
    tools = build_tools(client)
    return create_react_agent(llm, tools, checkpointer=checkpointer,
                              prompt=SYSTEM_PROMPT)
