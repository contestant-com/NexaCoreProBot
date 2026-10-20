import os
import random
import threading
import psycopg2
from datetime import datetime, date, timedelta
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
    return "NexaCore Ultimate Engine is Live!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)

# ----------------------------------------------------
# 2. Database Connection & Comprehensive Setup
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
                    status TEXT DEFAULT 'VIP',
                    expiry_date DATE
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
            cur.execute("SELECT expiry_date FROM subscribers WHERE user_id = %s;", (user_id,))
            res = cur.fetchone()
        conn.close()
        if res:
            if res[0] is None or res[0] >= date.today():
                return True
            return False
    return user_id in MEMORY_SUBSCRIBERS

def add_vip(user_id, days=30):
    MEMORY_SUBSCRIBERS.add(user_id)
    expiry = date.today() + timedelta(days=days)
    conn = get_db()
    if conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO subscribers (user_id, status, expiry_date) 
                VALUES (%s, 'VIP', %s) 
                ON CONFLICT (user_id) 
                DO UPDATE SET status = 'VIP', expiry_date = %s;
            """, (user_id, expiry, expiry))
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
                text=f"🔑 *Your Single-Use VIP Access Link:*\n{link.invite_link}\n\n*(Do not share this link)*",
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

    # Track Referral
    if context.args and not is_vip(user_id):
        try:
            referrer_id = int(context.args[0])
            if referrer_id != user_id:
                conn = get_db()
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("INSERT INTO referrals (user_id, referrer_id) VALUES (%s, %s) ON CONFLICT DO NOTHING;", (user_id, referrer_id))
                        cur.execute("UPDATE referrals SET invite_count = invite_count + 1 WHERE user_id = %s;", (referrer_id,))
                        conn.commit()
                    conn.close()
        except Exception:
            pass

    welcome_text = (
        f"✨ *Welcome to NexaCore Ecosystem!* ✨\n\n"
        f"Status: *{status}*\n\n"
        f"🤖 *VIP Features:*\n"
        f"• `/ask <query>` - AI Market & Assistant 🧠\n"
        f"• `/signals` - Daily VIP Alpha Signals 📈\n\n"
        f"🎁 *Earn & Monetize:*\n"
        f"• `/subscribe` - Unlock VIP Access (100 Stars) 🌟\n"
        f"• `/spin` - Daily Spin Wheel for Free VIP 🎡\n"
        f"• `/refer` - Invite friends & unlock VIP 🎁\n"
        f"• `/leaderboard` - Ambassador Rankings 🏆\n"
        f"• `/ad` - Support via Sponsored Ads 📺\n\n"
        f"💡 Type `/help` anytime!"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def ask_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_vip(user_id):
        await update.message.reply_text("🔒 *VIP Only:* Unlock full AI access with `/subscribe`!", parse_mode="Markdown")
        return

    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("💡 Usage: `/ask What is today's sentiment on BTC?`", parse_mode="Markdown")
        return

    responses = [
        f"🤖 *NexaCore AI Analysis:* Regarding '{query}', high volume signals suggest key support is holding strong.",
        f"🤖 *NexaCore AI Analysis:* Technical metrics for '{query}' indicate steady accumulation by top market wallets.",
    ]
    await update.message.reply_text(random.choice(responses), parse_mode="Markdown")

async def signals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_vip(user_id):
        await update.message.reply_text("🔒 *VIP Exclusive:* Upgrade via `/subscribe` to receive Daily Alpha Signals!", parse_mode="Markdown")
        return

    insight = (
        "📊 *NexaCore Daily VIP Signals*\n\n"
        "• *BTC/USDT:* Testing resistance. Bullish target active.\n"
        "• *ETH/USDT:* High layer-2 volume surge observed.\n"
        "• *Market Fear & Greed Index:* 72 (Greed)\n\n"
        "💡 *VIP Advice:* Manage leverage carefully today."
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
                await update.message.reply_text("⏳ You already spun today! Come back tomorrow for another chance.")
                conn.close()
                return
            cur.execute("""
                INSERT INTO daily_spins (user_id, last_spin) VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE SET last_spin = %s;
            """, (user_id, today, today))
            conn.commit()
        conn.close()

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📺 Watch Ad & Spin Wheel", callback_data="do_spin")]])
    await update.message.reply_text("🎡 *Daily VIP Spin Wheel*\n\nWatch a sponsored ad to spin for a chance at Free VIP Access!", reply_markup=keyboard, parse_mode="Markdown")

async def spin_callback(query_update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = query_update.callback_query
    await query.answer()
    user_id = query.from_user.id

    win = random.choices([True, False], weights=[25, 75])[0]
    if win and not is_vip(user_id):
        add_vip(user_id, days=30)
        await query.edit_message_text("🎉 *JACKPOT!* You won 1 Month Free VIP Access!", parse_mode="Markdown")
        await send_vip_invite(context.bot, user_id)
    else:
        await query.edit_message_text("🎰 You received *100 NexaPoints*! Spin again tomorrow!", parse_mode="Markdown")

async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ref_link = f"https://t.me/{context.bot.username}?start={user_id}"
    
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
        f"🎁 *NexaCore Referral Hub*\n\n"
        f"Your Referral Link:\n`{ref_link}`\n\n"
        f"Invited Friends: *{count}/3*\n"
    )
    if count >= 3 and not is_vip(user_id):
        add_vip(user_id, days=30)
        text += "\n🎉 *Bonus Unlocked: Free VIP Access Activated!*"
        await send_vip_invite(context.bot, user_id)
    elif count < 3:
        text += f"\nInvite *{3 - count} more friend(s)* to unlock Free VIP access!"

    await update.message.reply_text(text, parse_mode="Markdown")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    text = "🏆 *Top Ambassadors Leaderboard*\n\n"
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id, invite_count FROM referrals ORDER BY invite_count DESC LIMIT 5;")
            rows = cur.fetchall()
            if rows:
                for idx, row in enumerate(rows, 1):
                    text += f"{idx}. User `{row[0]}` — *{row[1]} Referrals*\n"
            else:
                text += "No referral data yet. Share `/refer` to be first!"
        conn.close()
    await update.message.reply_text(text, parse_mode="Markdown")

async def ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📺 *NexaCore Partner Ads*\n\nViewing partner announcements helps keep our free tier online!", parse_mode="Markdown")

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title="NexaCore VIP Membership",
        description="30-Day Pass: AI Assistant, Market Signals & Private VIP Group!",
        payload=f"NexaCore-Sub-{update.effective_chat.id}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice("1 Month VIP Access", 100)]
    )

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    add_vip(chat_id, days=30)
    await update.message.reply_text("🎉 *Payment Successful!* Your VIP membership is now ACTIVE for 30 days!", parse_mode="Markdown")
    await send_vip_invite(context.bot, chat_id)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return
    
    conn = get_db()
    vip_count = 0
    ref_count = 0
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM subscribers;")
            vip_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM referrals;")
            ref_count = cur.fetchone()[0]
        conn.close()

    await update.message.reply_text(f"📊 *NexaCore Admin Stats*\n\n• Total VIPs: *{vip_count}*\n• Total Referrers: *{ref_count}*", parse_mode="Markdown")

async def grant_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return

    target_id = update.effective_chat.id
    if context.args:
        try:
            target_id = int(context.args[0])
        except ValueError:
            return

    add_vip(target_id, days=30)
    await update.message.reply_text(f"👑 VIP status granted to `{target_id}` for 30 days!", parse_mode="Markdown")
    await send_vip_invite(context.bot, target_id)

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return

    msg = " ".join(context.args)
    if not msg:
        await update.message.reply_text("Usage: `/broadcast message`")
        return

    conn = get_db()
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id FROM subscribers;")
            rows = cur.fetchall()
        conn.close()

        count = 0
        for r in rows:
            try:
                await context.bot.send_message(chat_id=r[0], text=f"📢 *Announcement*\n\n{msg}", parse_mode="Markdown")
                count += 1
            except Exception:
                pass
        await update.message.reply_text(f"✅ Sent broadcast to {count} members!")

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
    app.add_handler(CommandHandler("ask", ask_ai))
    app.add_handler(CommandHandler("signals", signals))
    app.add_handler(CommandHandler("spin", spin))
    app.add_handler(CommandHandler("refer", refer))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("ad", ad))
    app.add_handler(CommandHandler("grant", grant_vip))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(spin_callback, pattern="^do_spin$"))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))

    print("🎻 NexaCore Ultimate Suite fully operational!")
    app.run_polling()

if __name__ == "__main__":
    main()
