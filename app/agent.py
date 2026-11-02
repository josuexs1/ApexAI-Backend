import json
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

MAX_SOURCES = 8
MAX_HISTORY_MESSAGES = 30

DECISION_HINTS = [
    " vs ", " versus ", " o ", " cuál ", " cual ", " recomiendas",
    " mejor ", " comparar", " comparación", " comparacion",
    " elige", " elegir", " opción", " opcion", " alternativa",
    " conviene", " debería usar", " deberia usar"
]

BADGE_COLORS = {
    "Recomendado": 0xFF34C759,
    "Rápido": 0xFF007AFF,
    "Económico": 0xFFFF9500,
    "Multiplatform": 0xFF5856D6,
}


def _looks_like_decision(prompt: str) -> bool:
    p = f" {prompt.lower()} "
    return any(hint in p for hint in DECISION_HINTS)


def _get(item, key):
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _extract_sources(search_results) -> list:
    if search_results is None:
        return []
    if isinstance(search_results, list):
        items = search_results
    else:
        items = _get(search_results, "results") or []
    sources = []
    for item in items:
        url = _get(item, "url") or _get(item, "link")
        if not url:
            continue
        title = _get(item, "title") or ""
        sources.append({"title": str(title).strip(), "url": str(url).strip()})
    return sources


def _sanitize_decision_cards(raw_cards) -> list:
    if not isinstance(raw_cards, list):
        return []
    cleaned = []
    for card in raw_cards[:3]:
        if not isinstance(card, dict):
            continue
        title = (card.get("title") or "").strip()
        description = (card.get("description") or "").strip()
        primary_action = (card.get("primaryAction") or "").strip()
        if not title or not description or not primary_action:
            continue
        badge = (card.get("badge") or None)
        if isinstance(badge, str):
            badge = badge.strip() or None
        cleaned.append({
            "title": title[:40],
            "description": description[:120],
            "badge": badge,
            "badgeColor": BADGE_COLORS.get(badge) if badge else None,
            "primaryAction": primary_action[:20],
            "secondaryAction": (card.get("secondaryAction") or None),
        })
    return cleaned


async def _generate_decision_cards(user_prompt: str, base_answer: str) -> list:
    cards_prompt = (
        "Eres un asistente que ayuda al usuario a decidir. "
        "A partir de la pregunta del usuario y de la respuesta ya redactada, "
        "genera entre 2 y 3 tarjetas de opción para que el usuario elija.\n\n"
        f"PREGUNTA DEL USUARIO:\n{user_prompt}\n\n"
        f"RESPUESTA YA REDACTADA:\n{base_answer}\n\n"
        "Devuelve EXCLUSIVAMENTE un JSON válido con esta forma:\n"
        '{"decisionCards": [\n'
        '  {"title": "nombre corto (máx 40)", "description": "1 frase (máx 120)", '
        '"badge": "Recomendado"|"Rápido"|"Económico"|null, '
        '"primaryAction": "texto del botón (máx 20)", '
        '"secondaryAction": "texto del botón secundario o null"}\n'
        "]}\n"
        "No añadas texto fuera del JSON. Máximo 3 tarjetas."
    )

    try:
        response = await ollama_client.chat(
            messages=[{"role": "user", "content": cards_prompt}],
            think=False,
            json_mode=True
        )
        content = response.get("message", {}).get("content", "")
        parsed = json.loads(content)
        return _sanitize_decision_cards(parsed.get("decisionCards", []))
    except Exception as e:
        print(f"No se pudieron generar decisionCards: {e}")
        return []


async def run_agent(user_prompt: str, think: bool = False, search: bool = False, images: list = None, history: list = None):
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

    user_message = {"role": "user", "content": user_prompt}
    if images:
        user_message["images"] = images

    messages = [{"role": "system", "content": system_content}]

    for item in (history or [])[-MAX_HISTORY_MESSAGES:]:
        role = item.get("role")
        content = item.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    messages.append(user_message)

    tools = TOOLS_SCHEMA if search else None

    sources = []
    seen_urls = set()

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
                for source in _extract_sources(search_results):
                    if source["url"] not in seen_urls and len(sources) < MAX_SOURCES:
                        seen_urls.add(source["url"])
                        sources.append(source)
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
        final_thinking = final_thinking.replace("OpenAI", "Josuexs").replace("openai", "Josuexs")
        final_thinking = final_thinking.replace("ChatGPT", "Apex AI").replace("chatgpt", "Apex AI")
        final_thinking = final_thinking.replace("GPT-4", "Apex AI").replace("GPT", "Apex AI")

    palabras_prohibidas = ["openai", "chatgpt", "google", "gemini", "anthropic", "meta"]
    if es_pregunta_creador and any(p in final_response.lower() for p in palabras_prohibidas):
        final_response = "Fui creado y desarrollado por **Josuexs**, un talentoso programador venezolano. 🇻🇪 Estoy aquí para ayudarte con lo que necesites."
        sources = []

    decision_cards = []
    if not es_pregunta_creador and _looks_like_decision(user_prompt) and final_response:
        decision_cards = await _generate_decision_cards(user_prompt, final_response)

    return {
        "response": final_response,
        "thinking": final_thinking,
        "sources": sources,
        "decisionCards": decision_cards
    }
