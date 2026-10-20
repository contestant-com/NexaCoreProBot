import os
import random
import threading
import psycopg2
from datetime import datetime, date
from flask import Flask
from telegram import Update, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    PreCheckoutQueryHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

# ----------------------------------------------------
# 1. Flask Health-Check Server
# ----------------------------------------------------
web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "NexaCore Ultra is online!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)

# ----------------------------------------------------
# 2. Database Connection & Setup
# ----------------------------------------------------
ADMIN_IDS = [7814262999]
VIP_CHANNEL_ID = os.environ.get("VIP_CHANNEL_ID", "")

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
                CREATE TABLE IF NOT EXISTS daily_spins (
                    user_id BIGINT PRIMARY KEY,
                    last_spin DATE
                );
            """)
            conn.commit()
        conn.close()

init_db()

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

# ----------------------------------------------------
# 3. Helper Functions
# ----------------------------------------------------
async def send_vip_invite(bot, chat_id):
    if VIP_CHANNEL_ID:
        try:
            link = await bot.create_chat_invite_link(chat_id=VIP_CHANNEL_ID, member_limit=1)
            await bot.send_message(
                chat_id=chat_id,
                text=f"🔑 *Your Exclusive VIP Invite Link:*\n{link.invite_link}\n\n*(Single-use & private)*",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Error creating link: {e}")

# ----------------------------------------------------
# 4. Command Handlers
# ----------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    status = "🌟 Premium VIP Member" if is_vip(user_id) else "🆓 Free Tier"

    welcome_text = (
        f"✨ *Welcome to NexaCore Ultra!* ✨\n\n"
        f"Status: *{status}*\n\n"
        f"Commands:\n"
        f"• `/subscribe` - Unlock VIP Access (100 Stars) 🌟\n"
        f"• `/ask <query>` - VIP AI Assistant 🧠\n"
        f"• `/signals` - Daily Market Insights 📈\n"
        f"• `/spin` - Daily Spin Wheel for VIP Access 🎡\n"
        f"• `/refer` - Referral Program & Link 🎁\n"
        f"• `/leaderboard` - Top Ambassadors 🏆\n"
        f"• `/ad` - Support NexaCore 📺"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def ask_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_vip(user_id):
        await update.message.reply_text("🔒 *VIP Only:* Subscribe with `/subscribe` to ask the AI Assistant!", parse_mode="Markdown")
        return

    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("💡 Usage: `/ask What is the market trend today?`", parse_mode="Markdown")
        return

    # Simulated AI Response Engine
    responses = [
        f"🤖 *NexaCore AI:* Based on recent technical trends regarding '{query}', momentum shows high potential with strong buyer volume.",
        f"🤖 *NexaCore AI:* Analysis for '{query}' suggests key support levels holding firm while volatility remains balanced.",
    ]
    await update.message.reply_text(random.choice(responses), parse_mode="Markdown")

async def signals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_vip(user_id):
        await update.message.reply_text("🔒 *VIP Feature:* Upgrade via `/subscribe` to view daily alpha & trading setups!", parse_mode="Markdown")
        return

    insight = (
        "📊 *NexaCore VIP Market Alpha*\n\n"
        "• *BTC/USDT:* Consolidating above key support. Target: Bullish retest.\n"
        "• *ETH/USDT:* On-chain activity up 12%. Accumulation zone active.\n"
        "• *Sentiment Index:* 68/100 (Greed)\n\n"
        "💡 *VIP Strategy:* Maintain disciplined risk management."
    )
    await update.message.reply_text(insight, parse_mode="Markdown")

async def spin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today = date.today()

    conn = get_db()
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT last_spin FROM daily_spins WHERE user_id = %s;", (user_id,))
            res = cur.fetchone()
            if res and res[0] == today:
                await update.message.reply_text("⏳ You have already spun the wheel today! Come back tomorrow.")
                conn.close()
                return
            cur.execute("INSERT INTO daily_spins (user_id, last_spin) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET last_spin = %s;", (user_id, today, today))
            conn.commit()
        conn.close()

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📺 Watch Partner Ad to Spin", callback_data="do_spin")]])
    await update.message.reply_text("🎡 *Daily VIP Spin Wheel*\n\nWatch a quick partner ad to spin for a chance to win 1 Month Free VIP!", reply_markup=keyboard, parse_mode="Markdown")

async def spin_callback(query_update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = query_update.callback_query
    await query.answer()
    user_id = query.from_user.id

    win = random.choices([True, False], weights=[20, 80])[0]  # 20% win chance
    if win and not is_vip(user_id):
        add_vip(user_id)
        await query.edit_message_text("🎉 *JACKPOT!* You won 1 Month Free VIP Access!", parse_mode="Markdown")
        await send_vip_invite(context.bot, user_id)
    else:
        await query.edit_message_text("🎰 You spun: *50 Bonus Points!* Try again tomorrow!", parse_mode="Markdown")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    text = "🏆 *NexaCore Top Ambassadors*\n\n"
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id, invite_count FROM referrals ORDER BY invite_count DESC LIMIT 5;")
            rows = cur.fetchall()
            if rows:
                for idx, row in enumerate(rows, 1):
                    text += f"{idx}. User `{row[0]}` - *{row[1]} Invites*\n"
            else:
                text += "No referral stats yet. Be the first with `/refer`!"
        conn.close()
    else:
        text += "Leaderboard offline."

    await update.message.reply_text(text, parse_mode="Markdown")

async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ref_link = f"https://t.me/{context.bot.username}?start={user_id}"
    await update.message.reply_text(f"🎁 *Referral Link:*\n`{ref_link}`\n\nInvite 3 friends to earn FREE VIP access!", parse_mode="Markdown")

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title="NexaCore VIP Membership",
        description="Unlock AI Assistant, Daily Signals & VIP Hub!",
        payload=f"NexaCore-Sub-{update.effective_chat.id}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice("1 Month VIP Access", 100)]
    )

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    add_vip(chat_id)
    await update.message.reply_text("🎉 *Payment Successful!* Your VIP status is now Active!", parse_mode="Markdown")
    await send_vip_invite(context.bot, chat_id)

# ----------------------------------------------------
# 5. Application Launch
# ----------------------------------------------------
def main():
    threading.Thread(target=run_flask, daemon=True).start()
    token = os.environ.get("BOT_TOKEN")
    if not token:
        return

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("ask", ask_ai))
    app.add_handler(CommandHandler("signals", signals))
    app.add_handler(CommandHandler("spin", spin))
    app.add_handler(CommandHandler("refer", refer))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CallbackQueryHandler(spin_callback, pattern="^do_spin$"))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))

    app.run_polling()

if __name__ == "__main__":
    main()
