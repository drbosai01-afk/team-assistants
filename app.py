"""
Главный файл: Telegram-бот + WebApp сервер.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import db
from agents import list_agents, chat_with_agent, AGENTS
from config import BOT_TOKEN, ADMIN_IDS, PUBLIC_URL, PORT, MODE, is_admin, webapp_url

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("team-assistants")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


def main_menu_kb(user_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🚀 Открыть приложение", web_app=WebAppInfo(url=webapp_url()))],
        [InlineKeyboardButton(text="📋 Агенты", callback_data="agents")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")],
    ]
    if is_admin(user_id):
        buttons.append([InlineKeyboardButton(
            text="⚙️ Админ-панель",
            web_app=WebAppInfo(url=f"{webapp_url()}admin.html"),
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    db.upsert_user(message.from_user.id, username=message.from_user.username,
                   first_name=message.from_user.first_name)
    role = "админ" if is_admin(message.from_user.id) else "клиент"
    await message.answer(
        f"👋 Привет, <b>{message.from_user.first_name or 'друг'}</b>!\n\n"
        f"Ты в команде из 3 ИИ-агентов. Открой приложение кнопкой ниже.\n\n"
        f"Твой режим: <b>{role}</b>",
        reply_markup=main_menu_kb(message.from_user.id),
    )


@dp.message(Command("agents"))
async def cmd_agents(message: types.Message):
    text = "<b>Твоя команда:</b>\n\n"
    for a in list_agents():
        text += f"{a.icon} <b>{a.name}</b> — {a.short}\n"
    text += "\nОткрой приложение → общайся с каждым."
    await message.answer(text, reply_markup=main_menu_kb(message.from_user.id))


@dp.callback_query(F.data == "agents")
async def cb_agents(cb: types.CallbackQuery):
    await cmd_agents(cb.message)
    await cb.answer()


@dp.callback_query(F.data == "help")
async def cb_help(cb: types.CallbackQuery):
    await cb.message.answer(
        "<b>Как пользоваться</b>\n\n"
        "1. Нажми «🚀 Открыть приложение»\n"
        "2. Выбери агента\n"
        "3. Пиши задачу\n"
        "4. История сохраняется\n\n"
        "Связка: Заказовод ведёт → Мастер делает → Ревьюер проверяет."
    )
    await cb.answer()


@dp.message(F.text)
async def fallback_text(message: types.Message):
    if not message.text or message.text.startswith("/"):
        return
    db.upsert_user(message.from_user.id, username=message.from_user.username,
                   first_name=message.from_user.first_name)
    await message.answer("🤔 Думаю...")
    reply = await chat_with_agent(AGENTS["zakazovod"], [], message.text)
    await message.answer(f"<b>📋 Заказовод:</b>\n\n{reply}")


# === FastAPI ===

WEBAPP_DIR = Path(__file__).parent / "webapp"


class ChatRequest(BaseModel):
    user_id: int
    agent_id: str
    message: str
    client_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    agent: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info(f"Запуск. Режим: {MODE}, Админы: {ADMIN_IDS}, URL: {PUBLIC_URL or '(не задан)'}")
    if MODE == "webhook" and PUBLIC_URL:
        await bot.set_webhook(f"{PUBLIC_URL}/telegram/webhook")
        log.info(f"Webhook: {PUBLIC_URL}/telegram/webhook")
    yield
    if MODE == "webhook":
        await bot.delete_webhook()


fastapi_app = FastAPI(title="Team Assistants", lifespan=lifespan)


@fastapi_app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    if MODE != "webhook":
        raise HTTPException(403, "webhook disabled")
    update = types.Update.model_validate(await request.json())
    await dp.feed_update(bot, update)
    return {"ok": True}


@fastapi_app.post("/api/chat", response_model=ChatResponse)
async def api_chat(req: ChatRequest):
    agent = AGENTS.get(req.agent_id)
    if not agent:
        raise HTTPException(400, "unknown agent")
    user = db.get_user(req.user_id)
    client_id = req.client_id or (user or {}).get("client_id")
    history_key = f"client:{client_id}" if client_id else str(req.user_id)
    history = db.get_history_by_client(client_id, req.agent_id, 20) if client_id else db.get_history(req.user_id, req.agent_id, 20)
    db.append_message(history_key, req.agent_id, "user", req.message)
    reply = await chat_with_agent(agent, history, req.message)
    db.append_message(history_key, req.agent_id, "assistant", reply)
    return ChatResponse(reply=reply, agent=agent.name)


@fastapi_app.get("/api/agents")
async def api_agents():
    return [{"id": a.id, "name": a.name, "icon": a.icon, "short": a.short} for a in list_agents()]


@fastapi_app.get("/api/history")
async def api_history(user_id: int, agent_id: str, client_id: str | None = None):
    if client_id:
        return db.get_history_by_client(client_id, agent_id, 50)
    return db.get_history(user_id, agent_id, 50)


class CreateClientRequest(BaseModel):
    owner_id: int
    name: str
    description: str = ""


@fastapi_app.post("/api/clients")
async def api_create_client(req: CreateClientRequest):
    if not is_admin(req.owner_id):
        raise HTTPException(403, "not admin")
    return db.create_client(req.name, req.owner_id, req.description)


@fastapi_app.get("/api/clients")
async def api_list_clients(owner_id: int):
    if not is_admin(owner_id):
        raise HTTPException(403, "not admin")
    return [c for c in db.list_clients() if c.get("owner_id") == owner_id]


class BindRequest(BaseModel):
    user_id: int
    client_id: str


@fastapi_app.post("/api/bind")
async def api_bind(req: BindRequest):
    db.upsert_user(req.user_id, client_id=req.client_id)
    db.add_user_to_client(req.user_id, req.client_id)
    return {"ok": True}


@fastapi_app.get("/api/me")
async def api_me(user_id: int):
    user = db.get_user(user_id)
    if not user:
        return {"user_id": user_id, "role": "guest", "client_id": None}
    role = "admin" if is_admin(user_id) else "client"
    return {**user, "role": role}


@fastapi_app.get("/webapp/")
@fastapi_app.get("/webapp/index.html")
async def webapp_index():
    return FileResponse(WEBAPP_DIR / "index.html")


@fastapi_app.get("/webapp/admin.html")
async def webapp_admin():
    return FileResponse(WEBAPP_DIR / "admin.html")


@fastapi_app.get("/webapp/chat.html")
async def webapp_chat():
    return FileResponse(WEBAPP_DIR / "chat.html")


fastapi_app.mount("/webapp/static", StaticFiles(directory=WEBAPP_DIR), name="webapp-static")


async def start_polling():
    log.info("Запуск бота в режиме polling...")
    await dp.start_polling(bot)


async def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не задан. Заполни .env")
        return
    import uvicorn
    config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    if MODE == "polling":
        await asyncio.gather(server.serve(), start_polling())
    else:
        await server.serve()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Остановлено")
