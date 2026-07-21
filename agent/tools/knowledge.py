from langchain_core.tools import tool

from rag.loader import get_vectorstore


def build_knowledge_tools():
    @tool
    async def retrieve_knowledge(query: str) -> str:
        """Tra cứu kiến thức về quy trình, quy tắc và hướng dẫn sử dụng hệ thống quản lý cầu lông.

        Dùng công cụ này khi admin hỏi về:
        - Quy trình tổ chức buổi đánh (tạo → mở đăng ký → tính tiền → show kết quả)
        - Cách nhập chi phí tính tiền
        - Ý nghĩa các trạng thái (is_selected, isCalculated, isShowMoney)
        - Quản lý suất nam/nữ
        - Các câu hỏi FAQ về hệ thống
        - Quy định và lưu ý chung

        KHÔNG dùng cho dữ liệu thực tế (danh sách ngày, người tham gia) — dùng list_categories / list_participants thay thế.
        """
        vectorstore = get_vectorstore()

        if vectorstore is None:
            return "Hệ thống đang khởi tạo kiến thức. Vui lòng thử lại sau vài giây."

        docs = vectorstore.similarity_search(query, k=4)

        if not docs:
            return "Không tìm thấy thông tin liên quan."

        return "\n\n---\n\n".join(
            f"Nội dung:\n{doc.page_content}"
            for doc in docs
        )

    return [retrieve_knowledge]
