from flask import Flask, request
import telebot
import sqlite3
import json
import os
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, WebAppInfo

app = Flask(__name__)

# CONFIGURATION
TOKEN = os.environ.get('TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 0))
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
    bot.send_message(message.chat.id, "<b>Welcome to MindEye AI!</b>", parse_mode="HTML", reply_markup=markup)

@bot.message_handler(commands=['send'])
def send_signal_admin(message):
    if message.from_user.id != ADMIN_ID: return
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Free", callback_data='send_free'), InlineKeyboardButton("Pro", callback_data='send_pro'))
    markup.add(InlineKeyboardButton("Premium", callback_data='send_premium'), InlineKeyboardButton("All", callback_data='send_all'))
    bot.reply_to(message, "Target Audience:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('send_'))
def admin_set_target(call):
    plan = call.data.split('_')[1]
    admin_states[call.from_user.id] = plan
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, f"Target: {plan.upper()}. Send signal:")

@bot.message_handler(func=lambda m: m.from_user.id in admin_states)
def broadcast_now(message):
    target = admin_states.pop(message.from_user.id)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE plan = ? OR ? = 'all'", (target, target))
        users = cursor.fetchall()
    for u in users:
        try: bot.copy_message(u[0], message.chat.id, message.message_id)
        except: continue
    bot.reply_to(message, f"Sent to {len(users)} users.")

@bot.message_handler(content_types=['web_app_data'])
def handle_app_events(message):
    data = json.loads(message.web_app_data.data)
    if data['action'] == 'subscribe':
        with get_db() as conn: conn.execute("INSERT OR REPLACE INTO users (user_id, plan) VALUES (?, ?)", (message.from_user.id, 'free'))
        bot.send_message(message.from_user.id, "✅ Subscribed to Free Signals!")
    elif data['action'] == 'buy_stars':
        prices = {'pro': 1499, 'premium': 2999} 
        bot.send_invoice(message.chat.id, f"MindEye {data['plan']}", "Access signals", f"plan_{data['plan']}", "", "XTR", [LabeledPrice("Price", prices[data['plan']])])

@bot.pre_checkout_query_handler(func=lambda query: True)
def process_checkout(query): bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def payment_done(message):
    plan = message.successful_payment.invoice_payload.split('_')[1]
    with get_db() as conn: conn.execute("UPDATE users SET plan = ? WHERE user_id = ?", (plan, message.chat.id))
    bot.send_message(message.chat.id, f"🎉 You are now {plan.upper()}!")

@app.route('/webhook', methods=['POST'])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return ''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
