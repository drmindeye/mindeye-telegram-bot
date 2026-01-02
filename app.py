from flask import Flask, request
import telebot
import sqlite3
import json
import os
from telebot.types import LabeledPrice

app = Flask(__name__)
TOKEN = os.environ.get('TOKEN')
# Add your Smart Glocal / Unlimit token to Render as PAYMENT_TOKEN
PAYMENT_TOKEN = os.environ.get('PAYMENT_TOKEN', '') 

bot = telebot.TeleBot(TOKEN, threaded=False)

def get_db():
    conn = sqlite3.connect('subscribers.db', check_same_thread=False)
    return conn

# Database init
with get_db() as conn:
    conn.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, plan TEXT DEFAULT "free")')

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "<b>Welcome to MindEye!</b> 🚀\n\nPlease use the <b>'Signals'</b> button at the bottom left to choose your plan.", parse_mode="HTML")

# --- THIS IS THE PART THAT CATCHES YOUR BUTTON CLICK ---
@bot.message_handler(content_types=['web_app_data'])
def handle_app_data(message):
    try:
        data = json.loads(message.web_app_data.data)
        user_id = message.from_user.id
        
        if data['action'] == 'subscribe':
            with get_db() as conn:
                conn.execute("INSERT OR REPLACE INTO users (user_id, plan) VALUES (?, ?)", (user_id, 'free'))
            bot.send_message(user_id, "✅ <b>Free Plan Active!</b>\nYou will receive signals here for 1 month.", parse_mode="HTML")
            
        elif data['action'] == 'buy':
            # Prices in Cents (1499 = $14.99)
            prices = {'pro': 1499, 'premium': 2999}
            bot.send_invoice(
                user_id,
                f"MindEye {data['plan'].upper()}",
                "Institutional signal access",
                f"plan_{data['plan']}",
                PAYMENT_TOKEN,
                "USD",
                [LabeledPrice("Subscription", prices[data['plan']])]
            )
    except Exception as e:
        bot.send_message(message.chat.id, "Error processing selection. Please use the Menu Button.")

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
