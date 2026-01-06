from flask import Flask, request
import telebot
import sqlite3
import json
import os
import threading
import time
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice

app = Flask(__name__)

# --- CONFIGURATION ---
TOKEN = os.environ.get('TOKEN')
ADMIN_ID = os.environ.get('ADMIN_ID')
# IMPORTANT: For Telegram Stars, this MUST be an empty string ""
PAYMENT_TOKEN = "" 

bot = telebot.TeleBot(TOKEN, threaded=False)
admin_states = {}

def get_db():
    conn = sqlite3.connect('subscribers.db', check_same_thread=False)
    return conn

# Initialize Database
with get_db() as conn:
    conn.execute('''CREATE TABLE IF NOT EXISTS users 
                  (user_id INTEGER PRIMARY KEY, 
                   plan TEXT DEFAULT 'free', 
                   expiry_date TEXT)''')

# --- BACKGROUND TASK: DEACTIVATION ---
def check_expirations():
    while True:
        try:
            now = datetime.now()
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id FROM users WHERE expiry_date < ? AND plan != 'expired'", (now.isoformat(),))
                expired_users = cursor.fetchall()
                for (u_id,) in expired_users:
                    conn.execute("UPDATE users SET plan = 'expired' WHERE user_id = ?", (u_id,))
                    try:
                        bot.send_message(u_id, "⚠️ <b>Subscription Expired</b>\nYour access has ended. Visit the Mini App to renew!")
                    except: pass
                conn.commit()
        except: pass
        time.sleep(86400)

threading.Thread(target=check_expirations, daemon=True).start()

# --- 1. USER COMMANDS ---
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "<b>Welcome to MindEye AI!</b> 🚀\nUse the menu button to open the app.", parse_mode="HTML")

@bot.message_handler(commands=['id'])
def get_id(m):
    bot.reply_to(m, f"🆔 Your ID: <code>{m.from_user.id}</code>", parse_mode="HTML")

# --- 2. ADMIN COMMANDS ---
@bot.message_handler(commands=['upgrade'])
def manual_upgrade(m):
    if str(m.from_user.id) != str(ADMIN_ID): return
    try:
        args = m.text.split()
        user_id, plan = args[1], args[2]
        expiry = (datetime.now() + timedelta(days=30)).isoformat()
        with get_db() as conn:
            conn.execute("INSERT OR REPLACE INTO users (user_id, plan, expiry_date) VALUES (?, ?, ?)", (user_id, plan, expiry))
        bot.send_message(m.chat.id, f"✅ Upgraded {user_id} to {plan}.")
        bot.send_message(user_id, f"🌟 Membership Activated for 30 days!")
    except:
        bot.reply_to(m, "Usage: /upgrade [ID] [pro/premium]")

@bot.message_handler(commands=['send'])
def admin_broadcast_start(message):
    if str(message.from_user.id) != str(ADMIN_ID): return
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Free", callback_data='send_free'), 
               InlineKeyboardButton("Pro", callback_data='send_pro'))
    markup.add(InlineKeyboardButton("Premium", callback_data='send_premium'), 
               InlineKeyboardButton("All", callback_data='send_all'))
    bot.reply_to(message, "📢 Select target:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('send_'))
def set_broadcast_target(call):
    admin_states[call.from_user.id] = call.data.split('_')[1]
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "Send message or photo now:")

@bot.message_handler(content_types=['text', 'photo'], func=lambda m: m.from_user.id in admin_states)
def perform_broadcast(message):
    target = admin_states.pop(message.from_user.id)
    with get_db() as conn:
        cursor = conn.cursor()
        if target == 'all': cursor.execute("SELECT user_id FROM users WHERE plan != 'expired'")
        else: cursor.execute("SELECT user_id FROM users WHERE plan = ?", (target,))
        users = cursor.fetchall()
    count = 0
    for (u_id,) in users:
        try:
            bot.copy_message(u_id, message.chat.id, message.message_id)
            count += 1
        except: continue
    bot.reply_to(message, f"✅ Sent to {count} users.")

# --- 3. MINI APP DATA (THE FIX) ---
@bot.message_handler(content_types=['web_app_data'])
def handle_app_data(message):
    try:
        web_data = json.loads(message.web_app_data.data)
        action = web_data.get('action')
        plan_type = web_data.get('plan')
        user_id = message.from_user.id
        expiry = (datetime.now() + timedelta(days=30)).isoformat()

        if action == 'subscribe':
            with get_db() as conn:
                conn.execute("INSERT OR REPLACE INTO users (user_id, plan, expiry_date) VALUES (?, 'free', ?)", (user_id, expiry))
            bot.send_message(user_id, "✅ <b>Free Plan Activated!</b>\nYour 30-day access is ready.", parse_mode="HTML")
            
        elif action == 'buy_stars':
            prices = {'pro': 555, 'premium': 1111}
            # Stars invoices require NO payment token
            bot.send_invoice(
                user_id, 
                title=f"MindEye {plan_type.capitalize()}", 
                description="1-Month Signal Access", 
                invoice_payload=f"plan_{plan_type}", 
                provider_token="", 
                currency="XTR", 
                prices=[LabeledPrice("Price", prices[plan_type])]
            )
    except Exception as e:
        # This will tell you exactly what is failing in the chat
        bot.send_message(message.chat.id, f"❌ System Error: {str(e)}")

@bot.pre_checkout_query_handler(func=lambda q: True)
def checkout(q): bot.answer_pre_checkout_query(q.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def success(m):
    plan = m.successful_payment.invoice_payload.split('_')[1]
    expiry = (datetime.now() + timedelta(days=30)).isoformat()
    with get_db() as conn:
        conn.execute("UPDATE users SET plan = ?, expiry_date = ? WHERE user_id = ?", (plan, expiry, m.chat.id))
    bot.send_message(m.chat.id, "🌟 <b>Payment Successful!</b> Access granted.")

# --- 4. WEBHOOK ---
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        update = telebot.types.Update.de_json(request.get_data().decode('utf-8'))
        bot.process_new_updates([update])
        return '', 200
    return 'Forbidden', 403

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
