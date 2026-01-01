from flask import Flask, request
import telebot
import sqlite3
import json
import os
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice

app = Flask(__name__)

# Configuration
TOKEN = os.environ.get('TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 0))
bot = telebot.TeleBot(TOKEN, threaded=False)

# Admin state tracker
admin_states = {}

# DB setup
def get_db():
    conn = sqlite3.connect('subscribers.db', check_same_thread=False)
    return conn

with get_db() as conn:
    conn.execute('''CREATE TABLE IF NOT EXISTS users 
                  (user_id INTEGER PRIMARY KEY, plan TEXT DEFAULT 'free')''')

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Welcome to MindEye Trading! Click the button below to open the Mini App.")

@bot.message_handler(commands=['subscribe'])
def subscribe(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Open MindEye App", web_app=telebot.types.WebAppInfo(url="YOUR_HTTPS_URL_HERE")))
    bot.reply_to(message, "Access our dashboard here:", reply_markup=markup)

# Admin send signal
@bot.message_handler(commands=['send'])
def send_signal(message):
    if message.from_user.id != ADMIN_ID:
        return
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Free", callback_data='send_free'))
    markup.add(InlineKeyboardButton("Pro", callback_data='send_pro'))
    markup.add(InlineKeyboardButton("Premium", callback_data='send_premium'))
    markup.add(InlineKeyboardButton("All", callback_data='send_all'))
    bot.reply_to(message, "Which group gets this signal?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('send_'))
def handle_send_callback(call):
    plan = call.data.split('_')[1]
    admin_states[call.from_user.id] = plan # Save target plan for this admin
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, f"Target: {plan.upper()}. Now type your signal text:")

# Handle the signal text broadcast
@bot.message_handler(func=lambda m: m.from_user.id in admin_states)
def broadcast_signal(message):
    target_plan = admin_states.pop(message.from_user.id) # Get target and clear state
    
    with get_db() as conn:
        cursor = conn.cursor()
        if target_plan == 'all':
            cursor.execute("SELECT user_id FROM users")
        else:
            cursor.execute("SELECT user_id FROM users WHERE plan = ?", (target_plan,))
        users = cursor.fetchall()

    count = 0
    for user in users:
        try:
            bot.send_message(user[0], message.text)
            count += 1
        except Exception:
            continue
    
    bot.reply_to(message, f"Signal broadcasted to {count} {target_plan} users.")

# Handling data sent from the Mini App
@bot.message_handler(content_types=['web_app_data'])
def handle_web_data(message):
    data = json.loads(message.web_app_data.data)
    user_id = message.from_user.id
    
    if data['action'] == 'subscribe' and data['plan'] == 'free':
        with get_db() as conn:
            conn.execute("INSERT OR REPLACE INTO users (user_id, plan) VALUES (?, ?)", (user_id, 'free'))
        bot.send_message(user_id, "You've joined the Free plan! 📊")

    elif data['action'] == 'buy_stars':
        prices = {'pro': 1499, 'premium': 2999}
        bot.send_invoice(
            chat_id=user_id,
            title=f"MindEye {data['plan'].capitalize()}",
            description=f"Subscription for {data['plan']} signals.",
            payload=f"plan_{data['plan']}",
            provider_token="", # Empty for Telegram Stars (XTR)
            currency="XTR",
            prices=[LabeledPrice(label="Price", amount=prices[data['plan']])]
        )

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    plan = message.successful_payment.invoice_payload.split('_')[1]
    with get_db() as conn:
        conn.execute("UPDATE users SET plan = ? WHERE user_id = ?", (plan, message.chat.id))
    bot.send_message(message.chat.id, f"Payment successful! You are now a {plan.upper()} member. 👑")

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        return 'Forbidden', 403

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
