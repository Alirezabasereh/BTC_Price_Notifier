from __future__ import annotations
import os
import logging
import requests
from typing import Optional

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("Missing BOT_TOKEN env var")

BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
DEFAULT_INTERVAL = 60  # seconds


def fetch_btc_usdt() -> float:
    resp = requests.get(BINANCE_TICKER_URL, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return float(data["price"])  # type: ignore


async def send_price(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id  # type: ignore
    try:
        price = fetch_btc_usdt()
        text = f"BTC/USDT: {price:.2f}"
    except Exception as e:
        logging.warning(f"price fetch failed: {e}")
        text = "⚠️ خطا در دریافت قیمت. تلاش مجدد در نوبت بعد."
    await context.bot.send_message(chat_id=chat_id, text=text)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    # اگر قبلاً job داشته، حذفش کنیم تا دوتایی نشه
    await stop(update, context, silent=True)

    interval = DEFAULT_INTERVAL
    if context.args:
        try:
            interval = max(10, int(context.args[0]))
        except Exception:
            pass

    context.job_queue.run_repeating(
        send_price,
        interval=interval,
        first=0,
        chat_id=chat_id,
        name=f"price_job_{chat_id}",
    )
    await update.message.reply_text(
        f"سلام! از الان هر {interval} ثانیه قیمت BTCUSDT رو برات می‌فرستم.\nدستورات: /now /interval <sec> /status /stop"
    )


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE, silent: bool = False):
    chat_id = update.effective_chat.id
    removed = False
    for job in context.job_queue.get_jobs_by_name(f"price_job_{chat_id}"):
        job.schedule_removal()
        removed = True
    if not silent:
        await update.message.reply_text("ارسال دوره‌ای متوقف شد." if removed else "فعلاً ارسال دوره‌ای فعالی نداشتیم.")


async def now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = fetch_btc_usdt()
        await update.message.reply_text(f"BTC/USDT: {price:.2f}")
    except Exception as e:
        await update.message.reply_text(f"⚠️ خطا در دریافت قیمت: {e}")


async def interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("فرمت: /interval <seconds> (حداقل 10)")
    try:
        seconds = max(10, int(context.args[0]))
    except Exception:
        return await update.message.reply_text("عدد نامعتبر است.")
    # ری‌استارت Job با بازه جدید
    await stop(update, context, silent=True)
    context.job_queue.run_repeating(
        send_price, interval=seconds, first=0, chat_id=update.effective_chat.id, name=f"price_job_{update.effective_chat.id}"
    )
    await update.message.reply_text(f"بازهٔ ارسال روی {seconds} ثانیه تنظیم شد.")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    jobs = context.job_queue.get_jobs_by_name(f"price_job_{chat_id}")
    if jobs:
        await update.message.reply_text("✅ ارسال دوره‌ای فعال است.")
    else:
        await update.message.reply_text("⏸️ ارسال دوره‌ای غیرفعال است.")


async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("now", now))
    app.add_handler(CommandHandler("interval", interval))
    app.add_handler(CommandHandler("status", status))

    await app.initialize()
    await app.start()
    try:
        await app.updater.start_polling()  # long polling
        await app.updater._bootstrap( )    # keep loop running
    finally:
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
