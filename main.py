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
    return "NexaCore Revenue Engine Live!", 200

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
                    tier TEXT DEFAULT 'Standard',
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

def get_user_tier(user_id):
    conn = get_db()
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT tier, expiry_date FROM subscribers WHERE user_id = %s;", (user_id,))
            res = cur.fetchone()
        conn.close()
        if res:
            tier, expiry = res
            if expiry is None or expiry >= date.today():
                return tier
    return None

def add_vip(user_id, tier='Standard', days=30):
    expiry = date.today() + timedelta(days=days)
    conn = get_db()
    if conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO subscribers (user_id, tier, expiry_date) 
                VALUES (%s, %s, %s) 
                ON CONFLICT (user_id) 
                DO UPDATE SET tier = %s, expiry_date = %s;
            """, (user_id, tier, expiry, tier, expiry))
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
                text=f"🔑 *Your Single-Use VIP Access Link:*\n{link.invite_link}\n\n*(Single-use only)*",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Error creating link: {e}")

# ----------------------------------------------------
# 4. Command Handlers
# ----------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tier = get_user_tier(user_id)
    status = f"🌟 VIP {tier} Member" if tier else "🆓 Free Tier"

    # Track Referral
    if context.args and not tier:
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
        f"✨ *Welcome to NexaCore Ultimate!* ✨\n\n"
        f"Status: *{status}*\n\n"
        f"💎 *Monetization & Upgrade Options:*\n"
        f"• `/subscribe` - Standard VIP (100 Stars) 🌟\n"
        f"• `/elite` - Elite AI & Signals VIP (250 Stars) 🔥\n"
        f"• `/buyinvite` - Instantly bypass 3 invites (40 Stars) ⚡\n"
        f"• `/ask` - Micro-transaction AI Query (5 Stars) 🤖\n\n"
        f"🎁 *Free Engagement:* `/spin`, `/refer`, `/leaderboard`"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title="NexaCore VIP Standard Pass",
        description="30-Day Access to Standard Signals & VIP Hub!",
        payload=f"Sub-Standard-{update.effective_chat.id}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice("VIP Standard (30 Days)", 100)]
    )

async def elite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title="NexaCore VIP Elite Pass",
        description="30-Day Access to Advanced AI Predictors & Direct Alerts!",
        payload=f"Sub-Elite-{update.effective_chat.id}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice("VIP Elite (30 Days)", 250)]
    )

async def buy_invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title="Instant Referral Bypass",
        description="Bypass the 3-invite rule and unlock Standard VIP instantly!",
        payload=f"Sub-Bypass-{update.effective_chat.id}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice("Instant VIP Unlock", 40)]
    )

async def ask_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tier = get_user_tier(user_id)
    
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("💡 Usage: `/ask What is the trend for BTC?` (Cost: 5 Stars for Free Users)", parse_mode="Markdown")
        return

    if tier:
        # VIPs get AI queries free
        await update.message.reply_text(f"🤖 *VIP AI Engine:* Detailed analysis for '{query}' shows high confidence bullish momentum across key timeframes.", parse_mode="Markdown")
    else:
        # Free users pay micro-transaction per query
        await context.bot.send_invoice(
            chat_id=update.effective_chat.id,
            title="AI Query Micro-Pass",
            description=f"Unlock instant AI analysis for: {query[:30]}...",
            payload=f"AI-Query-{update.effective_chat.id}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice("1 AI Analysis", 5)]
        )

async def signals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tier = get_user_tier(user_id)
    if not tier:
        await update.message.reply_text("🔒 *VIP Exclusive:* Upgrade via `/subscribe` or `/elite` to view market signals!", parse_mode="Markdown")
        return

    content = "📊 *NexaCore Elite Alpha Signals*\n\n• *BTC:* Breakout confirmed.\n• *ETH:* Whale accumulation active." if tier == 'Elite' else "📈 *NexaCore Standard Signals*\n\n• *BTC:* Consolidating in range."
    await update.message.reply_text(content, parse_mode="Markdown")

async def spin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today = date.today()
    conn = get_db()
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT last_spin FROM daily_spins WHERE user_id = %s;", (user_id,))
            res = cur.fetchone()
            if res and res[0] == today:
                await update.message.reply_text("⏳ Already spun today! Try again tomorrow.")
                conn.close()
                return
            cur.execute("INSERT INTO daily_spins (user_id, last_spin) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET last_spin = %s;", (user_id, today, today))
            conn.commit()
        conn.close()

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📺 Watch Partner Ad & Spin", callback_data="do_spin")]])
    await update.message.reply_text("🎡 *Daily Spin Wheel*\n\nWatch a sponsored partner ad for a chance to win Free VIP!", reply_markup=keyboard, parse_mode="Markdown")

async def spin_callback(query_update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = query_update.callback_query
    await query.answer()
    user_id = query.from_user.id

    win = random.choices([True, False], weights=[20, 80])[0]
    if win and not get_user_tier(user_id):
        add_vip(user_id, tier='Standard', days=30)
        await query.edit_message_text("🎉 *JACKPOT!* You won 30 Days Free VIP Standard!", parse_mode="Markdown")
        await send_vip_invite(context.bot, user_id)
    else:
        await query.edit_message_text("🎰 You won *50 NexaPoints*! Try again tomorrow.", parse_mode="Markdown")

async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ref_link = f"https://t.me/{context.bot.username}?start={user_id}"
    conn = get_db()
    count = 0
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT invite_count FROM referrals WHERE user_id = %s;", (user_id,))
            res = cur.fetchone()
            if res: count = res[0]
        conn.close()

    text = f"🎁 *Referral Program*\n\nYour Link:\n`{ref_link}`\n\nInvited: *{count}/3*\n"
    if count >= 3 and not get_user_tier(user_id):
        add_vip(user_id, tier='Standard', days=30)
        text += "\n🎉 *Goal reached! Free Standard VIP activated!*"
        await send_vip_invite(context.bot, user_id)
    elif count < 3:
        text += f"\nInvite *{3 - count} more* or use `/buyinvite` to skip!"

    await update.message.reply_text(text, parse_mode="Markdown")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    text = "🏆 *Top Ambassadors*\n\n"
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id, invite_count FROM referrals ORDER BY invite_count DESC LIMIT 5;")
            rows = cur.fetchall()
            if rows:
                for i, r in enumerate(rows, 1):
                    text += f"{i}. User `{r[0]}` — *{r[1]} invites*\n"
            else:
                text += "No records yet."
        conn.close()
    await update.message.reply_text(text, parse_mode="Markdown")

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    payload = update.message.successful_payment.invoice_payload

    if "Elite" in payload:
        add_vip(chat_id, tier='Elite', days=30)
        await update.message.reply_text("🔥 *Payment Successful!* VIP Elite status is now active!", parse_mode="Markdown")
        await send_vip_invite(context.bot, chat_id)
    elif "Standard" in payload or "Bypass" in payload:
        add_vip(chat_id, tier='Standard', days=30)
        await update.message.reply_text("🎉 *Payment Successful!* VIP Standard status is now active!", parse_mode="Markdown")
        await send_vip_invite(context.bot, chat_id)
    elif "AI-Query" in payload:
        await update.message.reply_text("🤖 *AI Micro-Query Unlocked:* Your custom analysis request has been processed successfully!", parse_mode="Markdown")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS: return
    msg = " ".join(context.args)
    if not msg:
        await update.message.reply_text("Usage: `/broadcast Your message here` (Sponsored ad slots)")
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
                await context.bot.send_message(chat_id=r[0], text=f"📢 *Sponsored Partner Announcement*\n\n{msg}", parse_mode="Markdown")
                count += 1
            except Exception: pass
        await update.message.reply_text(f"✅ Sponsored broadcast sent to {count} users!")

# ----------------------------------------------------
# 5. Initialization
# ----------------------------------------------------
def main():
    threading.Thread(target=run_flask, daemon=True).start()
    token = os.environ.get("BOT_TOKEN")
    if not token: return
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("elite", elite))
    app.add_handler(CommandHandler("buyinvite", buy_invite))
    app.add_handler(CommandHandler("ask", ask_ai))
    app.add_handler(CommandHandler("signals", signals))
    app.add_handler(CommandHandler("spin", spin))
    app.add_handler(CommandHandler("refer", refer))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(spin_callback, pattern="^do_spin$"))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))

    print("🎻 NexaCore Revenue Maximizer live!")
    app.run_polling()

if __name__ == "__main__":
    main()
