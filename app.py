from flask import Flask, request
import telebot
import sqlite3
import json
import os
from telebot.types import LabeledPrice

app = Flask(__name__)
TOKEN = os.environ.get('TOKEN')
ADMIN_ID = os.environ.get('ADMIN_ID')
PAYMENT_TOKEN = os.environ.get('PAYMENT_TOKEN', '') 

bot = telebot.TeleBot(TOKEN, threaded=False)

def get_db():
    conn = sqlite3.connect('subscribers.db', check_same_thread=False)
    return conn

with get_db() as conn:
    conn.execute('''CREATE TABLE IF NOT EXISTS users 
                  (user_id INTEGER PRIMARY KEY, plan TEXT DEFAULT 'free')''')

# --- HANDLES FREE PLAN & STARS INVOICE ---
@bot.message_handler(content_types=['web_app_data'])
def handle_app_data(message):
    try:
        data = json.loads(message.web_app_data.data)
        user_id = message.from_user.id
        
        if data['action'] == 'subscribe':
            with get_db() as conn:
                conn.execute("INSERT OR REPLACE INTO users (user_id, plan) VALUES (?, ?)", (user_id, 'free'))
            bot.send_message(user_id, "✅ <b>Free Plan Activated!</b>\nYou're now registered for 1 month of signals.")
            
        elif data['action'] == 'buy_stars':
            prices = {'pro': 555, 'premium': 1111}
            bot.send_invoice(
                user_id, 
                f"MindEye {data['plan'].capitalize()}", 
                "1-Month Signal Access", 
                f"plan_{data['plan']}", 
                "", "XTR", 
                [LabeledPrice("Price", prices[data['plan']])]
            )
    except Exception as e:
        print(f"Error: {e}")

# --- REST OF COMMANDS ---
@bot.message_handler(commands=['id'])
def get_id(m):
    bot.reply_to(m, f"Your ID: <code>{m.from_user.id}</code>", parse_mode="HTML")

@bot.message_handler(commands=['upgrade'])
def manual_upgrade(m):
    if str(m.from_user.id) != str(ADMIN_ID): return
    args = m.text.split()
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO users (user_id, plan) VALUES (?, ?)", (args[1], args[2]))
    bot.send_message(args[1], f"🌟 Your {args[2].upper()} plan is now ACTIVE!")

@bot.route('/webhook', methods=['POST'])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return '', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
