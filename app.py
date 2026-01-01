from flask import Flask, request
import telebot
import sqlite3
import json
import os
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, WebAppInfo

app = Flask(__name__)

# REPLACE WITH YOUR ACTUAL DATA
TOKEN = os.environ.get('8474378531:AAFDxtqbXZtz-bq6XAX67Pu5h-5JmGYfYzI')
ADMIN_ID = int(os.environ.get('637924570', 0))
# Your actual GitHub Pages URL
MINI_APP_URL = "https://drmindeye.github.io/mindeye-telegram-bot/" 

bot = telebot.TeleBot(TOKEN, threaded=False)
admin_states = {}

def get_db():
    conn = sqlite3.connect('subscribers.db', check_same_thread=False)
    return conn

with get_db() as conn:
    conn.execute('''CREATE TABLE IF NOT EXISTS users 
                  (user_id INTEGER PRIMARY KEY, plan TEXT DEFAULT 'free')''')

@bot.message_handler(commands=['start'])
def start(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🚀 Open MindEye Analyst", web_app=WebAppInfo(url=MINI_APP_URL)))
    bot.send_message(
        message.chat.id, 
        "<b>Welcome to MindEye AI Analyst!</b>\n\nYour all-in-one terminal for professional signals and trading bots.",
        parse_mode="HTML",
        reply_markup=markup
    )

@bot.message_handler(commands=['send'])
def send_signal_admin(message):
    if message.from_user.id != ADMIN_ID: return
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Free", callback_data='send_free'), InlineKeyboardButton("Pro", callback_data='send_pro'))
    markup.add(InlineKeyboardButton("Premium", callback_data='send_premium'), InlineKeyboardButton("All", callback_data='send_all'))
    bot.reply_to(message, "Select target audience for signal:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('send_'))
def admin_set_target(call):
    plan = call.data.split('_')[1]
    admin_states[call.from_user.id] = plan
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, f"Target: {plan.upper()}. Send the signal now:")

@bot.message_handler(func=lambda m: m.from_user.id in admin_states)
def broadcast_now(message):
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
    bot.reply_to(message, f"Signal sent to {count} users.")

@bot.message_handler(content_types=['web_app_data'])
def handle_app_events(message):
    data = json.loads(message.web_app_data.data)
    user_id = message.from_user.id
    
    if data['action'] == 'subscribe':
        with get_db() as conn:
            conn.execute("INSERT OR REPLACE INTO users (user_id, plan) VALUES (?, ?)", (user_id, 'free'))
        bot.send_message(user_id, "📈 You have successfully joined the Free Signals list!")

    elif data['action'] == 'buy_stars':
        prices = {'pro': 1499, 'premium': 2999} 
        bot.send_invoice(
            chat_id=user_id,
            title=f"MindEye {data['plan'].capitalize()}",
            description=f"Subscription for {data['plan']} trading signals.",
            payload=f"plan_{data['plan']}",
            provider_token="", 
            currency="XTR",
            prices=[LabeledPrice(label="Price", amount=prices[data['plan']])]
        )

@bot.pre_checkout_query_handler(func=lambda query: True)
def process_checkout(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def payment_done(message):
    plan = message.successful_payment.invoice_payload.split('_')[1]
    with get_db() as conn:
        conn.execute("UPDATE users SET plan = ? WHERE user_id = ?", (plan, message.chat.id))
    bot.send_message(message.chat.id, f"🎉 Payment Successful! Welcome to the {plan.upper()} group.")

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
        return ''
    return 'Forbidden', 403

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
