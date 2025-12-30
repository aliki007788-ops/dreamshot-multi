#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DreamShot Stars –全自动:
1) ایجاد فاکتور 100⭐️
2) دریافت SuccessfulPayment
3) تحویل فایل HD
"""
import os, json, io, asyncio, logging, hashlib, time
from pathlib import Path
from PIL import Image
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes, PreCheckoutQueryHandler
from aiohttp import web

# ---------- CONFIG ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL") + "/webhook"
HF_API = "https://api-inference.huggingface.co/models/OGk/RealESRGAN_x2"
HF_HEADERS = {"Authorization": f"Bearer {os.getenv('HF_TOKEN')}"}
LOCALES_DIR = Path(__file__).with_suffix('').parent / "locales"
HD_CACHE = Path("hd_cache"); HD_CACHE.mkdir(exist_ok=True)
STARS_AMOUNT = 100          # 100⭐️ ≈ 0.9 USD
PAYLOAD_HD = "hd_unlock"
logging.basicConfig(level=logging.INFO)
# ----------------------------

def load_locale(lang: str):
    with open(LOCALES_DIR / f"{lang}.json", encoding="utf-8") as f:
        return json.load(f)

def user_lang(update: Update) -> str:
    lang = update.effective_user.language_code or "en"
    return lang if lang in {"en", "fa", "ru", "ar", "hi"} else "en"

def dreamify(photo_bytes: bytes) -> bytes:
    resp = requests.post(HF_API, headers=HF_HEADERS, data=photo_bytes, timeout=30)
    resp.raise_for_status()
    return resp.content

def make_hd_path(photo_file_id: str) -> Path:
    """ مسیر ذخیره‌ی نسخه HD – نام فایل = hash file-id """
    return HD_CACHE / f"{photo_file_id}.jpg"

# ---------- HANDLERS ----------
async def start(update: Update, _: ContextTypes.DEFAULT_TYPE):
    lang = user_lang(update)
    loc = load_locale(lang)
    await update.message.reply_text(loc["start"], parse_mode="Markdown")

async def photo(update: Update, _: ContextTypes.DEFAULT_TYPE):
    lang = user_lang(update)
    loc = load_locale(lang)
    file = await update.message.photo[-1].get_file()
    photo_bytes = await file.download_as_bytearray()

    # ساخت نسخه رایگان 512
    free_bytes = await asyncio.get_event_loop().run_in_executor(None, dreamify, photo_bytes)
    keyboard = [[InlineKeyboardButton(loc["button_hd"], callback_data="create_invoice")]]
    await update.message.reply_photo(photo=free_bytes, caption=loc["caption"],
                                     reply_markup=InlineKeyboardMarkup(keyboard))

async def create_invoice(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """ ارسال فاکتور Stars """
    query = update.callback_query
    lang = user_lang(query)
    loc = load_locale(lang)
    await query.answer()
    chat_id = query.message.chat_id
    prices = [LabeledPrice("HD unlock", STARS_AMOUNT)]   # واحد = ستاره
    await _.bot.send_invoice(
        chat_id=chat_id,
        title="🔓 HD Unlock",
        description="Receive 4K cinematic version",
        payload=PAYLOAD_HD,
        provider_token="",           # برای Stars خالی بگذارید
        currency="XTR",              # XTR = Stars
        prices=prices,
        start_parameter="pay_hd"
    )

async def precheckout_handler(update: Update, _: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    if query.invoice_payload != PAYLOAD_HD:
        await query.answer(ok=False, error_message="Payload mismatch")
    else:
        await query.answer(ok=True)

async def successful_payment(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """ پرداخت موفق → تحویل HD """
    payment = update.message.successful_payment
    if payment.invoice_payload != PAYLOAD_HD:
        return
    photo_file_id = update.message.reply_to_message.photo[-1].file_id
    hd_path = make_hd_path(photo_file_id)
    if not hd_path.exists():
        # اگر HD ذخیره نشده بود، بساز
        file = await _.bot.get_file(photo_file_id)
        photo_bytes = await file.download_as_bytearray()
        hd_bytes = await asyncio.get_event_loop().run_in_executor(None, dreamify, photo_bytes)
        Image.open(io.BytesIO(hd_bytes)).save(hd_path, format="JPEG", quality=95)
    lang = user_lang(update)
    loc = load_locale(lang)
    with open(hd_path, "rb") as f:
        await update.message.reply_document(document=f,
                                            filename="DreamShot_HD.jpg",
                                            caption=loc.get("delivered", "✅ HD delivered!"))

# ---------- WEBHOOK ----------
async def webhook_handler(request):
    app = request.app["bot_app"]
    await app.update_queue.put(Update.de_json(await request.json(), app.bot))
    return web.Response(text="ok")

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, photo))
    application.add_handler(CallbackQueryHandler(create_invoice, pattern="^create_invoice$"))
    application.add_handler(PreCheckoutQueryHandler(precheckout_handler))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))

    # webhook
    from aiohttp import web
    aio_app = web.Application()
    aio_app["bot_app"] = application
    aio_app.router.add_post("/webhook", webhook_handler)

    port = int(os.getenv("PORT", 8000))
    application.run_webhook(listen="0.0.0.0", port=port,
                            webhook_url=os.getenv("RENDER_EXTERNAL_URL") + "/webhook",
                            drop_pending_updates=True)
    web.run_app(aio_app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
