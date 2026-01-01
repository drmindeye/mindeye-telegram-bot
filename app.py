from flask import Flask, request
import telebot
import sqlite3
import json
import os
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, WebAppInfo

app = Flask(__name__)

# CONFIGURATION - Pulls from Render Environment Variables
TOKEN = os.environ.get('TOKEN')
ADMIN_ID = os.environ.get('ADMIN_ID') 
MINI_APP_URL = "https://drmindeye.github.io/mindeye-telegram-bot/" 

bot = telebot.TeleBot(TOKEN, threaded=False)
admin_states = {}

def get_db():
    conn = sqlite3.connect('subscribers.db', check_same_thread=False)
    return conn

# Initialize Database
with get_db() as conn:
    conn.execute('''CREATE TABLE IF NOT EXISTS users 
                  (user_id INTEGER PRIMARY KEY, plan TEXT DEFAULT 'free')''')

@bot.message_handler(commands=['start'])
def start(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🚀 Open MindEye Analyst", web_app=WebAppInfo(url=MINI_APP_URL)))
    bot.send_message(message.chat.id, "<b>Welcome to MindEye AI Analyst!</b>\n\nYour terminal for institutional grade signals.", parse_mode="HTML", reply_markup=markup)

# --- ADMIN SIGNAL BROADCASTING ---
@bot.message_handler(commands=['send'])
def admin_broadcast_start(message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Free (1 Pair)", callback_data='send_free'))
    markup.add(InlineKeyboardButton("Pro (3 Pairs)", callback_data='send_pro'))
    markup.add(InlineKeyboardButton("Premium (6 Pairs)", callback_data='send_premium'))
    markup.add(InlineKeyboardButton("All Users", callback_data='send_all'))
    bot.reply_to(message, "📢 <b>New Signal Broadcast</b>\nSelect target group:", parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('send_'))
def set_broadcast_target(call):
    target = call.data.split('_')[1]
    admin_states[call.from_user.id] = target
    bot.answer_callback_query(call.id)
    
    details = {
        'free': "FREE (2-3 signals/week)",
        'pro': "PRO (3-7 signals/week)",
        'premium': "PREMIUM (7-12 signals/week)",
        'all': "ALL SUBSCRIBERS"
    }
    
    bot.send_message(call.message.chat.id, f"🎯 Target: <b>{details[target]}</b>\n\nSend the signal (Text, Photo, or Chart) now:", parse_mode="HTML")

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
        except:
            continue
    bot.reply_to(message, f"✅ Signal successfully sent to {count} users.")

# --- MINI APP DATA HANDLING ---
@bot.message_handler(content_types=['web_app_data'])
def handle_app_data(message):
    data = json.loads(message.web_app_data.data)
    user_id = message.from_user.id
    
    if data['action'] == 'subscribe':
        with get_db() as conn:
            conn.execute("INSERT OR REPLACE INTO users (user_id, plan) VALUES (?, ?)", (user_id, 'free'))
        bot.send_message(user_id, "📈 <b>Success!</b>\nYou are registered for the 1-Month Free Plan (2-3 signals/week).", parse_mode="HTML")

    elif data['action'] == 'buy_stars':
        prices = {'pro': 1499, 'premium': 2999} 
        bot.send_invoice(
            chat_id=user_id,
            title=f"MindEye {data['plan'].capitalize()}",
            description=f"Monthly access to {data['plan']} signals.",
            payload=f"plan_{data['plan']}",
            provider_token="", 
            currency="XTR",
            prices=[LabeledPrice(label="Monthly Subscription", amount=prices[data['plan']])]
        )

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout_ok(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def payment_success(message):
    plan = message.successful_payment.invoice_payload.split('_')[1]
    with get_db() as conn:
        conn.execute("UPDATE users SET plan = ? WHERE user_id = ?", (plan, message.chat.id))
    bot.send_message(message.chat.id, f"🌟 <b>Payment Confirmed!</b>\nWelcome to the {plan.upper()} group. You will now receive high-frequency signals.", parse_mode="HTML")

# --- WEBHOOK ROUTE ---
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    return 'Forbidden', 403

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
