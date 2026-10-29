from app.ollama_client import ollama_client
from app.config import settings

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Busca en la web información actualizada y en tiempo real.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "La consulta de búsqueda. Sé específico."
                    }
                },
                "required": ["query"]
            }
        }
    }
]

async def run_agent(user_prompt: str, think: bool = False, search: bool = False):
    messages = [{"role": "user", "content": user_prompt}]
    tools = TOOLS_SCHEMA if search else None
    
    response = await ollama_client.chat(messages=messages, tools=tools, think=think)
    assistant_message = response.get("message", {})
    messages.append(assistant_message)

    iterations = 0
    while assistant_message.get("tool_calls") and iterations < settings.MAX_AGENT_ITERATIONS:
        iterations += 1
        for tool_call in assistant_message["tool_calls"]:
            function_name = tool_call["function"]["name"]
            arguments = tool_call["function"]["arguments"]

            if function_name == "web_search":
                search_results = await ollama_client.web_search(query=arguments.get("query", ""))
                messages.append({
                    "role": "tool",
                    "tool_name": function_name,
                    "content": str(search_results)
                })

        response = await ollama_client.chat(messages=messages, tools=tools, think=think)
        assistant_message = response.get("message", {})
        messages.append(assistant_message)

    return {
        "response": assistant_message.get("content", ""),
        "thinking": assistant_message.get("thinking", "")
    }