import json


def json_response(data, message: str = "", status_code: int = 200) -> str:
    return json.dumps(
        {"status_code": status_code, "message": message, "data": data},
        ensure_ascii=False,
    )


def build_tools(client):
    from agent.tools.categories import build_category_tools
    from agent.tools.participants import build_participant_tools
    from agent.tools.finance import build_finance_tools
    from agent.tools.knowledge import build_knowledge_tools

    return (
        build_category_tools(client)
        + build_participant_tools(client)
        + build_finance_tools(client)
        + build_knowledge_tools()
    )


__all__ = ["json_response", "build_tools"]
