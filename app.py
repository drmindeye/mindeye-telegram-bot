from flask import Flask, request
import telebot
import sqlite3
import json
import os
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, WebAppInfo

app = Flask(__name__)

# CONFIGURATION
TOKEN = os.environ.get('TOKEN')
ADMIN_ID = os.environ.get('ADMIN_ID') 
MINI_APP_URL = "https://drmindeye.github.io/mindeye-telegram-bot/" 

bot = telebot.TeleBot(TOKEN, threaded=False)
admin_states = {}

def get_db():
    conn = sqlite3.connect('subscribers.db', check_same_thread=False)
    return conn

# Database Initialization
with get_db() as conn:
    conn.execute('''CREATE TABLE IF NOT EXISTS users 
                  (user_id INTEGER PRIMARY KEY, plan TEXT DEFAULT 'free')''')

@bot.message_handler(commands=['start'])
def start(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🚀 Open MindEye Analyst", web_app=WebAppInfo(url=MINI_APP_URL)))
    bot.send_message(message.chat.id, "<b>Welcome to MindEye AI Analyst!</b>\nYour institutional trading companion.", parse_mode="HTML", reply_markup=markup)

# --- ADMIN SIGNAL BROADCASTING ---
@bot.message_handler(commands=['send'])
def admin_broadcast_start(message):
    if str(message.from_user.id) != str(ADMIN_ID):
        bot.reply_to(message, "❌ Access Denied.")
        return
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Free Users", callback_data='send_free'))
    markup.add(InlineKeyboardButton("Pro Users", callback_data='send_pro'))
    markup.add(InlineKeyboardButton("Premium Users", callback_data='send_premium'))
    markup.add(InlineKeyboardButton("All Users", callback_data='send_all'))
    bot.reply_to(message, "📢 <b>Signal Console</b>\nSelect target group:", parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('send_'))
def set_broadcast_target(call):
    target = call.data.split('_')[1]
    admin_states[call.from_user.id] = target
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, f"🎯 Target: {target.upper()}\nSend the signal content (text/image/chart) now:")

@bot.message_handler(func=lambda m: m.from_user.id in admin_states)
def perform_broadcast(message):
    target = admin_states.pop(message.from_user.id)
    with get_db() as conn:
        cursor = conn.cursor()
        if target == 'all':
            cursor.execute("SELECT user_id FROM users")
        else:
            cursor.execute("SELECT user_id FROM users WHERE plan = ?", (target,))
        users = cursor.fetchall()

    count = 0
    for u in users:
        try:
            bot.copy_message(u[0], message.chat.id, message.message_id)
            count += 1
        except: continue
    bot.reply_to(message, f"✅ Signal successfully sent to {count} users.")

# --- MINI APP DATA & PAYMENTS ---
@bot.message_handler(content_types=['web_app_data'])
def handle_app_data(message):
    data = json.loads(message.web_app_data.data)
    user_id = message.from_user.id
    
    if data['action'] == 'subscribe':
        with get_db() as conn:
            conn.execute("INSERT OR REPLACE INTO users (user_id, plan) VALUES (?, ?)", (user_id, 'free'))
        bot.send_message(user_id, "✅ <b>Registered!</b>\nYou'll receive 2-3 free signals per week for 1 month.", parse_mode="HTML")

    elif data['action'] == 'buy_stars':
        # Pro: $14.99 (~555 Stars) | Premium: $29.99 (~1111 Stars)
        prices_map = {'pro': 555, 'premium': 1111} 
        bot.send_invoice(
            chat_id=user_id,
            title=f"MindEye {data['plan'].capitalize()} Plan",
            description=f"1-Month subscription for {data['plan']} signals.",
            payload=f"plan_{data['plan']}",
            provider_token="", 
            currency="XTR", 
            prices=[LabeledPrice(label="Monthly Access", amount=prices_map[data['plan']])]
        )

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout_ok(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def payment_success(message):
    plan = message.successful_payment.invoice_payload.split('_')[1]
    with get_db() as conn:
        conn.execute("UPDATE users SET plan = ? WHERE user_id = ?", (plan, message.chat.id))
    bot.send_message(message.chat.id, f"🌟 <b>Payment Confirmed!</b>\nWelcome to {plan.upper()}. You are now set for the month!", parse_mode="HTML")

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
        return ''
    return 'Forbidden', 403

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
