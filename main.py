import os
import threading
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# 1. Tiny Flask web server to satisfy Render's free health check
web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "NexaCore is live!", 200

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)

# 2. Telegram Bot setup
TOKEN = os.environ.get("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 Welcome to NexaCore!\n\n"
        "Use /help to view all commands."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start - Start NexaCore\n"
        "/crypto - Crypto tools\n"
        "/price - Check prices\n"
        "/tasks - Productivity tools\n"
        "/create - Creative assistant\n"
        "/news - Latest news\n"
        "/about - About NexaCore"
    )

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "NexaCore is an AI-powered productivity, business and crypto assistant."
    )

if __name__ == "__main__":
    # Start web server in a background thread
    threading.Thread(target=run_web_server, daemon=True).start()

    # Start Telegram Bot
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("about", about))

    print("NexaCore is running...")
    app.run_polling()
