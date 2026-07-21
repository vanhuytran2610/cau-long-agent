import os

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from agent.tools import build_tools
from content.prompts import get_system_prompt

XAI_MODEL = os.environ.get("XAI_MODEL", "grok-4.3")


def build_agent(
    client,
    checkpointer,
    language: str = "vi",
    memory_context: str = "",
):
    """One agent per request, bound to the calling admin's access token."""
    llm = ChatOpenAI(
        model=XAI_MODEL,
        api_key=os.environ["XAI_API_KEY"],
        base_url="https://api.x.ai/v1",
        temperature=0,
    )
    tools = build_tools(client)

    system_prompt = get_system_prompt(language)
    if memory_context:
        system_prompt += f"\n\n[Lịch sử liên quan từ các buổi trước]\n{memory_context}"
    system_prompt += (
        "\n\nYou have access to a knowledge base via the retrieve_knowledge tool. "
        "Always use it when the question relates to website content, documentation, "
        "or stored knowledge before answering."
    )

    return create_react_agent(llm, tools, checkpointer=checkpointer, prompt=system_prompt)
