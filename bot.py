from __future__ import annotations
import os
import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# تنظیم لاگ
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("❌ BOT_TOKEN تنظیم نشده است.")

BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
DEFAULT_INTERVAL = 60  # ثانیه

def fetch_btc_usdt() -> float:
    resp = requests.get(BINANCE_TICKER_URL, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return float(data["price"])

async def send_price(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]
    try:
        price = fetch_btc_usdt()
        text = f"💰 BTC/USDT: {price:.2f} USD"
    except Exception as e:
        logging.warning(f"Price fetch failed: {e}")
        text = "⚠️ خطا در دریافت قیمت."
    await context.bot.send_message(chat_id=chat_id, text=text)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # بررسی فعال بودن JobQueue
    if context.job_queue is None:
        await update.message.reply_text("❌ JobQueue فعال نیست. کتابخانه را با [job-queue] نصب کنید.")
        return

    # حذف jobهای قبلی
    for job in context.job_queue.get_jobs_by_name(f"price_job_{chat_id}"):
        job.schedule_removal()

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
        data={"chat_id": chat_id},
        name=f"price_job_{chat_id}",
    )

    await update.message.reply_text(
        f"✅ از الان هر {interval} ثانیه قیمت BTC رو می‌فرستم.\n"
        f"دستورات: /now /interval <sec> /status /stop"
    )

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if context.job_queue:
        removed = False
        for job in context.job_queue.get_jobs_by_name(f"price_job_{chat_id}"):
            job.schedule_removal()
            removed = True
        await update.message.reply_text("⏹️ ارسال دوره‌ای متوقف شد." if removed else "⏹️ ارسالی فعال نبود.")
    else:
        await update.message.reply_text("❌ JobQueue فعال نیست.")

async def now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = fetch_btc_usdt()
        await update.message.reply_text(f"💰 BTC/USDT: {price:.2f} USD")
    except Exception as e:
        await update.message.reply_text(f"⚠️ خطا در دریافت قیمت: {e}")

async def interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("فرمت: /interval <seconds> (حداقل 10)")
    try:
        seconds = max(10, int(context.args[0]))
    except Exception:
        return await update.message.reply_text("عدد نامعتبر است.")
    chat_id = update.effective_chat.id
    if context.job_queue:
        for job in context.job_queue.get_jobs_by_name(f"price_job_{chat_id}"):
            job.schedule_removal()
        context.job_queue.run_repeating(
            send_price,
            interval=seconds,
            first=0,
            data={"chat_id": chat_id},
            name=f"price_job_{chat_id}",
        )
        await update.message.reply_text(f"🔄 بازهٔ ارسال روی {seconds} ثانیه تنظیم شد.")
    else:
        await update.message.reply_text("❌ JobQueue فعال نیست.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if context.job_queue:
        jobs = context.job_queue.get_jobs_by_name(f"price_job_{chat_id}")
        await update.message.reply_text("✅ ارسال دوره‌ای فعال است." if jobs else "⏸️ ارسال دوره‌ای غیرفعال است.")
    else:
        await update.message.reply_text("❌ JobQueue فعال نیست.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("now", now))
    app.add_handler(CommandHandler("interval", interval))
    app.add_handler(CommandHandler("status", status))

    logging.info("🚀 Starting bot with polling ...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
