#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DreamShot Multi-Lingual Serverless Bot
Deploy on Render (or any ASGI runner) → webhook
"""
import os, json, io, asyncio, logging
from pathlib import Path
from PIL import Image
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from aiohttp import web

# ---------- CONFIG ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL", "https://yourapp.onrender.com") + "/webhook"
PAYMENT_LINK = os.getenv("PAYMENT_LINK", "https://zarinp.al/yourlink")  # یا کوین‌پی
HF_API = "https://api-inference.huggingface.co/models/OGk/RealESRGAN_x2"
HF_HEADERS = {"Authorization": f"Bearer {os.getenv('HF_TOKEN')}"}
LOCALES_DIR = Path(__file__).with_suffix('').parent / "locales"
logging.basicConfig(level=logging.INFO)
# ----------------------------

def load_locale(lang: str):
    with open(LOCALES_DIR / f"{lang}.json", encoding="utf-8") as f:
        return json.load(f)

def user_lang(update: Update) -> str:
    # اگر چت خصوصی باشه زبان تلگرام رو می‌گیریم
    lang = update.effective_user.language_code or "en"
    if lang not in {"en", "fa", "ru", "ar", "hi"}:
        lang = "en"
    return lang

def dreamify(photo_bytes: bytes) -> bytes:
    resp = requests.post(HF_API, headers=HF_HEADERS, data=photo_bytes, timeout=30)
    resp.raise_for_status()
    return resp.content

# ---------- HANDLERS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = user_lang(update)
    loc = load_locale(lang)
    await update.message.reply_text(loc["start"], parse_mode="Markdown")

async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = user_lang(update)
    loc = load_locale(lang)
    file = await update.message.photo[-1].get_file()
    photo_bytes = await file.download_as_bytearray()
    new_bytes = await asyncio.get_event_loop().run_in_executor(None, dreamify, photo_bytes)
    keyboard = [[InlineKeyboardButton(loc["button_hd"], callback_data="hd")]]
    await update.message.reply_photo(photo=new_bytes,
                                     caption=loc["caption"],
                                     reply_markup=InlineKeyboardMarkup(keyboard))

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = user_lang(query)
    loc = load_locale(lang)
    await query.answer()
    if query.data == "hd":
        await query.edit_message_caption(caption=loc["pay_msg"],
                                         reply_markup=InlineKeyboardMarkup([[
                                             InlineKeyboardButton(loc["button_hd"], url=PAYMENT_LINK)
                                         ]]))

# ---------- WEBHOOK ----------
async def webhook_handler(request):
    """ aiohttp webhook """
    app = request.app["bot_app"]
    await app.update_queue.put(Update.de_json(await request.json(), app.bot))
    return web.Response(text="ok")

def main():
    # ساخت اپلیکیشن
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, photo))
    application.add_handler(CallbackQueryHandler(button))

    # webhook
    from aiohttp import web
    aio_app = web.Application()
    aio_app["bot_app"] = application
    aio_app.router.add_post("/webhook", webhook_handler)

    # اجرای webhook
    port = int(os.getenv("PORT", 8000))
    application.run_webhook(listen="0.0.0.0", port=port,
                            webhook_url=WEBHOOK_URL,
                            drop_pending_updates=True)
    web.run_app(aio_app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()