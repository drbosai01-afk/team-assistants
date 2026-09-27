"""
Конфигурация и LLM клиент.

Поддерживает:
- groq       (Llama, БЕСПЛАТНО, через ВПН) — рекомендую для РФ
- openrouter (Claude/GPT, нужна карта + ВПН)
- openai     (прямой OpenAI)
- proxy      (любой OpenAI-совместимый)
- gigachat   (Сбер, РФ без ВПН)
"""

import os
from dotenv import load_dotenv

load_dotenv()

# === Telegram ===
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ADMIN_IDS: list[int] = [
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
]

# === Деплой ===
PUBLIC_URL: str = os.getenv("PUBLIC_URL", "").rstrip("/")
PORT: int = int(os.getenv("PORT", "8080"))
MODE: str = os.getenv("MODE", "polling")

# === LLM ===
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "groq").lower()
LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
LLM_MODEL: str = os.getenv("LLM_MODEL", "llama-3.1-70b-versatile")
LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "")

# GigaChat
GIGACHAT_CREDENTIALS: str = os.getenv("GIGACHAT_CREDENTIALS", "")
GIGACHAT_SCOPE: str = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
GIGACHAT_MODEL: str = os.getenv("GIGACHAT_MODEL", "GigaChat-Pro")

# === Инициализация клиента ===
client = None
gigachat_client = None

if LLM_PROVIDER == "gigachat":
    try:
        from gigachat import GigaChat
        gigachat_client = GigaChat(
            credentials=GIGACHAT_CREDENTIALS,
            scope=GIGACHAT_SCOPE,
            model=GIGACHAT_MODEL,
            profanity_check=False,
            timeout=60,
        )
    except ImportError:
        print("pip install gigachat")
    except Exception as e:
        print(f"GigaChat init error: {e}")

elif LLM_PROVIDER == "groq":
    from openai import AsyncOpenAI
    client = AsyncOpenAI(
        api_key=LLM_API_KEY,
        base_url="https://api.groq.com/openai/v1",
    )

elif LLM_PROVIDER == "openrouter":
    from openai import AsyncOpenAI
    client = AsyncOpenAI(
        api_key=LLM_API_KEY,
        base_url="https://openrouter.ai/api/v1",
    )

elif LLM_PROVIDER == "openai":
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=LLM_API_KEY)

elif LLM_PROVIDER == "proxy":
    from openai import AsyncOpenAI
    client = AsyncOpenAI(
        api_key=LLM_API_KEY or "not-required",
        base_url=LLM_BASE_URL or "https://api.openai.com/v1",
    )


# === Вызов LLM ===

async def call_llm(system, messages, temperature=0.7, max_tokens=2000):
    if LLM_PROVIDER == "gigachat":
        return await _call_gigachat(system, messages, temperature, max_tokens)

    if client is None:
        return "LLM не инициализирован. Проверь .env"

    try:
        full_messages = [{"role": "system", "content": system}] + messages
        response = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Ошибка LLM: {str(e)[:200]}"


async def _call_gigachat(system, messages, temperature, max_tokens):
    if gigachat_client is None:
        return "GigaChat не инициализирован"

    try:
        from gigachat.models import Chat, MessagesRole, Message
        chat = Chat(
            messages=[
                Message(role=MessagesRole.SYSTEM, content=system),
                *[
                    Message(
                        role=MessagesRole.USER if m["role"] == "user" else MessagesRole.ASSISTANT,
                        content=m["content"],
                    )
                    for m in messages
                ],
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        response = gigachat_client.chat(chat)
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"GigaChat error: {str(e)[:200]}"


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def webapp_url() -> str:
    if PUBLIC_URL:
        return f"{PUBLIC_URL}/webapp/"
    return f"http://localhost:{PORT}/webapp/"


def provider_info() -> str:
    if LLM_PROVIDER == "gigachat":
        return f"GigaChat ({GIGACHAT_MODEL})"
    return f"{LLM_PROVIDER} ({LLM_MODEL})"
