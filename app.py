from flask import Flask, request
import telebot
import sqlite3
import json
import os
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice

app = Flask(__name__)
TOKEN = os.environ.get('TOKEN')
ADMIN_ID = os.environ.get('ADMIN_ID')
PAYMENT_TOKEN = os.environ.get('PAYMENT_TOKEN', '') 

bot = telebot.TeleBot(TOKEN, threaded=False)
admin_states = {}

def get_db():
    conn = sqlite3.connect('subscribers.db', check_same_thread=False)
    return conn

with get_db() as conn:
    conn.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, plan TEXT DEFAULT 'free')''')

@bot.message_handler(commands=['start'])
def start(message):
    # THIS LINE LOGS THE ID TO RENDER
    print(f"NEW USER: {message.from_user.first_name} | ID: {message.from_user.id}")
    bot.send_message(message.chat.id, f"Welcome {message.from_user.first_name}! Open the Signals menu to start.")

@bot.message_handler(commands=['upgrade'])
def upgrade(message):
    if str(message.from_user.id) != str(ADMIN_ID): return
    try:
        args = message.text.split()
        with get_db() as conn:
            conn.execute("INSERT OR REPLACE INTO users (user_id, plan) VALUES (?, ?)", (args[1], args[2]))
        bot.send_message(message.chat.id, f"✅ User {args[1]} upgraded to {args[2]}.")
        bot.send_message(args[1], f"🌟 Membership activated!")
    except:
        bot.reply_to(message, "Use: /upgrade ID plan")

@bot.message_handler(content_types=['web_app_data'])
def handle_app_data(message):
    data = json.loads(message.web_app_data.data)
    if data['action'] == 'subscribe':
        with get_db() as conn:
            conn.execute("INSERT OR REPLACE INTO users (user_id, plan) VALUES (?, ?)", (message.from_user.id, 'free'))
        bot.send_message(message.from_user.id, "✅ Free plan activated!")
    elif data['action'] == 'buy_stars':
        prices = {'pro': 555, 'premium': 1111}
        bot.send_invoice(message.from_user.id, f"MindEye {data['plan']}", "1-Month Access", f"plan_{data['plan']}", "", "XTR", [LabeledPrice("Price", prices[data['plan']])])

@bot.pre_checkout_query_handler(func=lambda q: True)
def checkout(q): bot.answer_pre_checkout_query(q.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def success(m):
    plan = m.successful_payment.invoice_payload.split('_')[1]
    with get_db() as conn:
        conn.execute("UPDATE users SET plan = ? WHERE user_id = ?", (plan, m.chat.id))
    bot.send_message(m.chat.id, "🌟 Payment Successful!")

@app.route('/webhook', methods=['POST'])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return '', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
