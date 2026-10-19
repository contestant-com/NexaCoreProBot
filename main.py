import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")

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

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_cmd))
app.add_handler(CommandHandler("about", about))

print("NexaCore is running...")
app.run_polling()
