"""
Suggestion chips shown to the admin as tappable buttons.

Each entry maps a short button label -> a sample command the frontend sends
to POST /agent when tapped. Keep this list in sync with the tools in agent.py;
it's the user-facing menu of what the agent can do.

`prompt` is what gets sent as the chat message. For write actions the agent
will still ask for confirmation (per the system prompt), so these sample
prompts are safe to fire directly.
"""

_SUGGESTIONS = {
    "vi": [
        {
            "id": "list_dates",
            "label": "📋 Xem các ngày đánh",
            "prompt": "Liệt kê tất cả các ngày đánh hiện có.",
            "category": "read",
        },
        {
            "id": "list_participants",
            "label": "👥 Ai đã đăng ký?",
            "prompt": "Ngày đánh gần nhất có những ai đăng ký tham gia?",
            "category": "read",
        },
        {
            "id": "create_date",
            "label": "➕ Tạo ngày đánh",
            "prompt": "Tạo một ngày đánh mới. Hỏi mình thông tin cần thiết nhé.",
            "category": "write",
        },
        {
            "id": "calculate",
            "label": "💰 Tính tiền",
            "prompt": "Mình muốn tính tiền cho một ngày đánh. Hỏi mình thông tin buổi đánh nhé.",
            "category": "write",
        },
        {
            "id": "show_result",
            "label": "📢 Show kết quả",
            "prompt": "Mình muốn cho user xem kết quả tiền của một ngày đánh.",
            "category": "write",
        },
        {
            "id": "edit_date",
            "label": "✏️ Sửa ngày đánh",
            "prompt": "Mình muốn sửa thông tin một ngày đánh.",
            "category": "write",
        },
    ],
    "en": [
        {
            "id": "list_dates",
            "label": "📋 View sessions",
            "prompt": "List all current badminton sessions.",
            "category": "read",
        },
        {
            "id": "list_participants",
            "label": "👥 Who registered?",
            "prompt": "Who has registered for the most recent session?",
            "category": "read",
        },
        {
            "id": "create_date",
            "label": "➕ Create session",
            "prompt": "Create a new badminton session. Ask me for the necessary details.",
            "category": "write",
        },
        {
            "id": "calculate",
            "label": "💰 Calculate fees",
            "prompt": "I want to calculate fees for a session. Ask me for the session details.",
            "category": "write",
        },
        {
            "id": "show_result",
            "label": "📢 Show results",
            "prompt": "I want to show the fee results for a session to users.",
            "category": "write",
        },
        {
            "id": "edit_date",
            "label": "✏️ Edit session",
            "prompt": "I want to edit a session's details.",
            "category": "write",
        },
    ],
}


def get_suggestions(language: str = "vi") -> list:
    return _SUGGESTIONS.get(language, _SUGGESTIONS["vi"])
