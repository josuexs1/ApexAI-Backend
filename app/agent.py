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
    prompt_lower = user_prompt.lower()
    preguntas_creador = [
        "quien te creo", "quién te creó", "quien te hizo", "quién te hizo", 
        "quien te desarrollo", "quién te desarrolló", "tu creador", "de donde eres", 
        "openai", "gpt", "chatgpt", "google", "gemini"
    ]
    es_pregunta_creador = any(p in prompt_lower for p in preguntas_creador)

    system_content = settings.SYSTEM_PROMPT
    if es_pregunta_creador:
        system_content += (
            "\n\n[MODO ESTRICTO ACTIVADO]: El usuario está preguntando por tu origen o identidad. "
            "Recuerda: Eres Apex AI, creado por Josuexs de Venezuela. "
            "ESTÁ ESTRICTAMENTE PROHIBIDO mencionar a OpenAI, Google, Meta o cualquier otra empresa de IA. "
            "Si intentas mencionarlos, estarás fallando a tu creador."
        )

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_prompt}
    ]
    
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

    final_response = assistant_message.get("content", "")
    final_thinking = assistant_message.get("thinking", "")

    if final_thinking:
        final_thinking = final_thinking.replace("OpenAI", "Josuexs")
        final_thinking = final_thinking.replace("openai", "Josuexs")
        final_thinking = final_thinking.replace("ChatGPT", "Apex AI")
        final_thinking = final_thinking.replace("chatgpt", "Apex AI")
        final_thinking = final_thinking.replace("GPT-4", "Apex AI")
        final_thinking = final_thinking.replace("GPT", "Apex AI")

    palabras_prohibidas = ["openai", "chatgpt", "google", "gemini", "anthropic", "meta"]
    if es_pregunta_creador and any(p in final_response.lower() for p in palabras_prohibidas):
        final_response = "Fui creado y desarrollado por **Josuexs**, un talentoso programador venezolano. 🇻🇪 Estoy aquí para ayudarte con lo que necesites."

    return {
        "response": final_response,
        "thinking": final_thinking
    }
