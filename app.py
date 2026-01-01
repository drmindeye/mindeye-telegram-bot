from flask import Flask, request
import telebot
import sqlite3
import json
import os
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, WebAppInfo

app = Flask(__name__)

TOKEN = os.environ.get('TOKEN')
ADMIN_ID = os.environ.get('ADMIN_ID') 
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
    # IMPORTANT: Ensure users open the app through the Menu Button for full clickability
    markup.add(InlineKeyboardButton("🚀 Open MindEye Analyst", web_app=WebAppInfo(url=MINI_APP_URL)))
    bot.send_message(message.chat.id, "<b>Welcome to MindEye AI Analyst!</b>\nPlease use the Menu Button below for the best experience.", parse_mode="HTML", reply_markup=markup)

@bot.message_handler(commands=['send'])
def admin_broadcast_start(message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Free", callback_data='send_free'), InlineKeyboardButton("Pro", callback_data='send_pro'))
    markup.add(InlineKeyboardButton("Premium", callback_data='send_premium'))
    markup.add(InlineKeyboardButton("All", callback_data='send_all'))
    bot.reply_to(message, "📢 Select target group for signal:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('send_'))
def set_broadcast_target(call):
    target = call.data.split('_')[1]
    admin_states[call.from_user.id] = target
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, f"🎯 Target: {target.upper()}\nSend signal content now:")

@bot.message_handler(func=lambda m: m.from_user.id in admin_states)
def perform_broadcast(message):
    target = admin_states.pop(message.from_user.id)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users" if target == 'all' else "SELECT user_id FROM users WHERE plan = ?", (target,) if target != 'all' else ())
        users = cursor.fetchall()
    count = 0
    for u in users:
        try:
            bot.copy_message(u[0], message.chat.id, message.message_id)
            count += 1
        except: continue
    bot.reply_to(message, f"✅ Sent to {count} users.")

@bot.message_handler(content_types=['web_app_data'])
def handle_app_data(message):
    data = json.loads(message.web_app_data.data)
    user_id = message.from_user.id
    if data['action'] == 'subscribe':
        with get_db() as conn:
            conn.execute("INSERT OR REPLACE INTO users (user_id, plan) VALUES (?, ?)", (user_id, 'free'))
        bot.send_message(user_id, "✅ <b>Registered!</b>\n1-Month Free Plan active.", parse_mode="HTML")
    elif data['action'] == 'buy_stars':
        prices_map = {'pro': 555, 'premium': 1111} 
        bot.send_invoice(user_id, f"MindEye {data['plan'].capitalize()}", "1-Month Access", f"plan_{data['plan']}", "", "XTR", [LabeledPrice("Price", prices_map[data['plan']])])

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout_ok(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
        return ''
    return 'Forbidden', 403

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
