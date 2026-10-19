import os
import threading
from flask import Flask
from telegram import Update, LabeledPrice
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    PreCheckoutQueryHandler,
    MessageHandler,
    filters,
)

# ----------------------------------------------------
# 1. Flask Health-Check Server (For Render Deployment)
# ----------------------------------------------------
web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "NexaCore is online and running smoothly!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)

# ----------------------------------------------------
# 2. Database Storage & Admin Configuration
# ----------------------------------------------------
SUBSCRIBERS = set()
ADMIN_IDS = [7814262999]  # Your Telegram UID

# ----------------------------------------------------
# 3. Bot Handlers & Automated Logic
# ----------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    status = "🌟 Premium VIP Member" if user_id in SUBSCRIBERS else "🆓 Free Tier"
    
    welcome_text = (
        f"✨ *Welcome to NexaCore!* ✨\n\n"
        f"Your Current Status: *{status}*\n\n"
        f"Commands:\n"
        f"• `/subscribe` - Unlock Premium VIP Access with Stars 🌟\n"
        f"• `/crypto` - Latest Crypto Market Updates\n"
        f"• `/help` - Learn more about NexaCore"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends automated payment invoice for Telegram Stars."""
    chat_id = update.effective_chat.id
    
    title = "NexaCore VIP Membership"
    description = "Unlock unlimited AI queries, crypto signals & premium group features!"
    payload = f"NexaCore-Sub-{chat_id}"
    currency = "XTR"  # Telegram Stars
    prices = [LabeledPrice("1 Month VIP Access", 100)]  # 100 Stars

    await context.bot.send_invoice(
        chat_id=chat_id,
        title=title,
        description=description,
        payload=payload,
        provider_token="",  # Blank required for Telegram Stars
        currency=currency,
        prices=prices
    )

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Answers payment pre-checkout query automatically."""
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Automatically grants access upon successful payment."""
    chat_id = update.effective_chat.id
    SUBSCRIBERS.add(chat_id)
    
    await update.message.reply_text(
        "🎉 *Payment Successful!* 🎉\n\n"
        "Your NexaCore VIP access is now **Active**! Enjoy all premium features.",
        parse_mode="Markdown"
    )

async def grant_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually grants VIP access to a user (Admin only)."""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Unauthorized command.")
        return

    if not context.args:
        # If no user ID provided, grant access to yourself
        SUBSCRIBERS.add(update.effective_chat.id)
        await update.message.reply_text("👑 VIP status granted to yourself instantly!")
        return

    try:
        target_id = int(context.args[0])
        SUBSCRIBERS.add(target_id)
        await update.message.reply_text(f"✅ Successfully granted VIP status to user `{target_id}`!", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("❌ Invalid User ID. Usage: `/grant 123456789`", parse_mode="Markdown")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends broadcast messages to active users (Admin only)."""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Unauthorized command.")
        return

    msg = " ".join(context.args)
    if not msg:
        await update.message.reply_text("Usage: `/broadcast Your sponsored message here`", parse_mode="Markdown")
        return

    count = 0
    for sub_id in SUBSCRIBERS:
        try:
            await context.bot.send_message(chat_id=sub_id, text=f"📢 *Sponsored Broadcast*\n\n{msg}", parse_mode="Markdown")
            count += 1
        except Exception:
            pass

    await update.message.reply_text(f"✅ Broadcast sent successfully to {count} users!")

# ----------------------------------------------------
# 4. Application Initialization
# ----------------------------------------------------
def main():
    # Start Flask server in background thread
    threading.Thread(target=run_flask, daemon=True).start()

    token = os.environ.get("BOT_TOKEN")
    if not token:
        print("ERROR: BOT_TOKEN environment variable is missing!")
        return

    app = Application.builder().token(token).build()

    # Register handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("grant", grant_vip))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))

    print("🎻 NexaCore is live and running perfectly!")
    app.run_polling()

if __name__ == "__main__":
    main()
