import json

from langchain_core.messages import AIMessage, ToolMessage

TARGET_TOOLS = {"create_vote_date", "add_participant", "calculate"}


def extract_events(messages: list) -> list[dict]:
    # Build map: tool_call_id → {name, args}
    call_map: dict[str, dict] = {}
    for msg in messages:
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            for tc in msg.tool_calls:
                if tc["name"] in TARGET_TOOLS:
                    call_map[tc["id"]] = {"name": tc["name"], "args": tc["args"]}

    events = []
    for msg in messages:
        if not isinstance(msg, ToolMessage):
            continue
        tc = call_map.get(msg.tool_call_id)
        if not tc:
            continue

        try:
            content = json.loads(msg.content)
        except Exception:
            continue

        if content.get("status_code") not in (200, 201):
            continue

        args = tc["args"]
        name = tc["name"]

        if name == "create_vote_date":
            text = (
                f"Admin tạo buổi đánh '{args['name']}'. "
                f"Nội dung: {args.get('content') or 'không có'}. "
                f"Mở vote: {'có' if args.get('is_selected') else 'không'}."
            )
            events.append({
                "event_type": "create_session",
                "text": text,
                "metadata": {
                    "session_name": args["name"],
                    "content": args.get("content", ""),
                },
            })

        elif name == "add_participant":
            text = (
                f"Admin thêm {args['name']} "
                f"(giới tính: {args.get('gender', '?')}, "
                f"trình độ: {args.get('level') or 'không rõ'}) vào buổi đánh."
            )
            events.append({
                "event_type": "add_participant",
                "text": text,
                "metadata": {
                    "participant_name": args["name"],
                    "gender": args.get("gender"),
                    "level": args.get("level"),
                },
            })

        elif name == "calculate":
            text = (
                f"Tính tiền buổi đánh. "
                f"Thông tin thanh toán: {args.get('payment_info', '')}."
            )
            events.append({
                "event_type": "calculate",
                "text": text,
                "metadata": {
                    "payment_info": args.get("payment_info", ""),
                },
            })

    return events
