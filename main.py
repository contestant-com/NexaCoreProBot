import os
import threading
import psycopg2
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
# 1. Flask Health-Check Server
# ----------------------------------------------------
web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "NexaCore is online and running smoothly!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)

# ----------------------------------------------------
# 2. Database Connection & Admin Config
# ----------------------------------------------------
ADMIN_IDS = [7814262999]  # Your Telegram UID
VIP_CHANNEL_ID = os.environ.get("VIP_CHANNEL_ID", "")  # e.g., -100xxxxxxxxxx

def get_db():
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        return psycopg2.connect(db_url, sslmode='require')
    return None

def init_db():
    conn = get_db()
    if conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS subscribers (
                    user_id BIGINT PRIMARY KEY,
                    status TEXT DEFAULT 'VIP'
                );
                CREATE TABLE IF NOT EXISTS referrals (
                    user_id BIGINT PRIMARY KEY,
                    referrer_id BIGINT,
                    invite_count INT DEFAULT 0
                );
            """)
            conn.commit()
        conn.close()

init_db()

# Memory fallback if DB is not attached yet
MEMORY_SUBSCRIBERS = set()

def is_vip(user_id):
    conn = get_db()
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id FROM subscribers WHERE user_id = %s;", (user_id,))
            res = cur.fetchone()
        conn.close()
        return res is not None
    return user_id in MEMORY_SUBSCRIBERS

def add_vip(user_id):
    MEMORY_SUBSCRIBERS.add(user_id)
    conn = get_db()
    if conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO subscribers (user_id) VALUES (%s) ON CONFLICT DO NOTHING;", (user_id,))
            conn.commit()
        conn.close()

def get_all_vips():
    conn = get_db()
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id FROM subscribers;")
            rows = cur.fetchall()
        conn.close()
        return [r[0] for r in rows]
    return list(MEMORY_SUBSCRIBERS)

# ----------------------------------------------------
# 3. Helper: Generate VIP Invite Link
# ----------------------------------------------------
async def send_vip_invite(bot, chat_id):
    if VIP_CHANNEL_ID:
        try:
            link = await bot.create_chat_invite_link(
                chat_id=VIP_CHANNEL_ID,
                member_limit=1
            )
            await bot.send_message(
                chat_id=chat_id,
                text=f"🔑 *Your Exclusive VIP Group Invite Link:*\n{link.invite_link}\n\n*(This link is single-use and valid only for you)*",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Error creating invite link: {e}")

# ----------------------------------------------------
# 4. Bot Handlers
# ----------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    status = "🌟 Premium VIP Member" if is_vip(user_id) else "🆓 Free Tier"
    
    # Handle Referral tracking
    if context.args and not is_vip(user_id):
        try:
            referrer_id = int(context.args[0])
            if referrer_id != user_id:
                conn = get_db()
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO referrals (user_id, referrer_id) VALUES (%s, %s)
                            ON CONFLICT DO NOTHING;
                        """, (user_id, referrer_id))
                        cur.execute("UPDATE referrals SET invite_count = invite_count + 1 WHERE user_id = %s;", (referrer_id,))
                        conn.commit()
                    conn.close()
        except Exception:
            pass

    welcome_text = (
        f"✨ *Welcome to NexaCore!* ✨\n\n"
        f"Your Current Status: *{status}*\n\n"
        f"Commands:\n"
        f"• `/subscribe` - Unlock Premium VIP Access (100 Stars) 🌟\n"
        f"• `/refer` - Invite 3 friends for FREE VIP Access 🎁\n"
        f"• `/ad` - Support NexaCore & view rewarded partner ads 📺\n"
        f"• `/crypto` - Market Updates & Signals 📈\n"
        f"• `/help` - Learn more about NexaCore"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generates unique referral link for user."""
    user_id = update.effective_user.id
    bot_username = context.bot.username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    
    count = 0
    conn = get_db()
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT invite_count FROM referrals WHERE user_id = %s;", (user_id,))
            res = cur.fetchone()
            if res:
                count = res[0]
        conn.close()

    text = (
        f"🎁 *NexaCore Referral Program*\n\n"
        f"Share your link with friends:\n`{ref_link}`\n\n"
        f"Invited Friends: *{count}/3*\n"
    )
    if count >= 3 and not is_vip(user_id):
        add_vip(user_id)
        text += "\n🎉 *Congratulations! You earned 1 Month of Free VIP Access!*"
        await send_vip_invite(context.bot, user_id)
    elif count < 3:
        text += f"\nInvite *{3 - count} more friend(s)* to unlock VIP for FREE!"

    await update.message.reply_text(text, parse_mode="Markdown")

async def ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """AdsGram Rewarded Ad Trigger for Free Users."""
    await update.message.reply_text(
        "📺 *Watch Ads to Support NexaCore*\n\n"
        "Click below to view sponsored partner announcements!",
        parse_mode="Markdown"
    )

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends payment invoice for 100 Stars."""
    chat_id = update.effective_chat.id
    
    await context.bot.send_invoice(
        chat_id=chat_id,
        title="NexaCore VIP Membership",
        description="Unlock unlimited AI queries, crypto signals & private VIP group!",
        payload=f"NexaCore-Sub-{chat_id}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice("1 Month VIP Access", 100)]
    )

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    add_vip(chat_id)
    
    await update.message.reply_text(
        "🎉 *Payment Successful!* 🎉\n\n"
        "Your NexaCore VIP access is now **Active**!",
        parse_mode="Markdown"
    )
    await send_vip_invite(context.bot, chat_id)

async def grant_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin only grant command."""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Unauthorized command.")
        return

    target_id = update.effective_chat.id
    if context.args:
        try:
            target_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ Invalid ID.")
            return

    add_vip(target_id)
    await update.message.reply_text(f"👑 VIP status granted to `{target_id}`!", parse_mode="Markdown")
    await send_vip_invite(context.bot, target_id)

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin broadcast system."""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Unauthorized command.")
        return

    msg = " ".join(context.args)
    if not msg:
        await update.message.reply_text("Usage: `/broadcast Your message here`", parse_mode="Markdown")
        return

    vips = get_all_vips()
    count = 0
    for sub_id in vips:
        try:
            await context.bot.send_message(chat_id=sub_id, text=f"📢 *Sponsored Broadcast*\n\n{msg}", parse_mode="Markdown")
            count += 1
        except Exception:
            pass

    await update.message.reply_text(f"✅ Broadcast sent to {count} users!")

# ----------------------------------------------------
# 5. Initialization
# ----------------------------------------------------
def main():
    threading.Thread(target=run_flask, daemon=True).start()

    token = os.environ.get("BOT_TOKEN")
    if not token:
        print("ERROR: BOT_TOKEN missing!")
        return

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("grant", grant_vip))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("refer", refer))
    app.add_handler(CommandHandler("ad", ad))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))

    print("🎻 NexaCore Full Edition is live!")
    app.run_polling()

if __name__ == "__main__":
    main()
