from flask import Flask, request
import telebot
import sqlite3
import json
import os
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, WebAppInfo

app = Flask(__name__)

# CONFIGURATION - Replace with your actual values
TOKEN = os.environ.get('TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 0))
# The URL where your GitHub index.html is hosted
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
    markup.add(InlineKeyboardButton("🚀 Launch MindEye Analyst", web_app=WebAppInfo(url=MINI_APP_URL)))
    bot.send_message(
        message.chat.id, 
        "Welcome to MindEye AI Analyst! \n\nProfessional Signals, Bots, and Management at your fingertips.",
        reply_markup=markup
    )

@bot.message_handler(commands=['send'])
def send_signal_init(message):
    if message.from_user.id != ADMIN_ID: return
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Free", callback_data='send_free'), InlineKeyboardButton("Pro", callback_data='send_pro'))
    markup.add(InlineKeyboardButton("Premium", callback_data='send_premium'), InlineKeyboardButton("All Users", callback_data='send_all'))
    bot.reply_to(message, "📡 SELECT TARGET AUDIENCE:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('send_'))
def handle_admin_choice(call):
    plan = call.data.split('_')[1]
    admin_states[call.from_user.id] = plan
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, f"Target set to: {plan.upper()}\nNow send the Signal message (text, images, etc):")

@bot.message_handler(func=lambda m: m.from_user.id in admin_states)
def broadcast_action(message):
    target_plan = admin_states.pop(message.from_user.id)
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
            bot.copy_message(user[0], message.chat.id, message.message_id)
            count += 1
        except: continue
    bot.reply_to(message, f"✅ Successfully broadcasted to {count} users.")

@bot.message_handler(content_types=['web_app_data'])
def handle_app_data(message):
    data = json.loads(message.web_app_data.data)
    user_id = message.from_user.id
    
    if data['action'] == 'subscribe':
        with get_db() as conn:
            conn.execute("INSERT OR REPLACE INTO users (user_id, plan) VALUES (?, ?)", (user_id, 'free'))
        bot.send_message(user_id, "✅ You are now registered for Free Signals!")

    elif data['action'] == 'buy_stars':
        prices = {'pro': 1499, 'premium': 2999} # Price in Telegram Stars
        bot.send_invoice(
            chat_id=user_id,
            title=f"MindEye {data['plan'].capitalize()} Plan",
            description=f"Full access to {data['plan']} signals and analytics.",
            payload=f"plan_{data['plan']}",
            provider_token="", # Empty for Stars
            currency="XTR",
            prices=[LabeledPrice(label="Subscription", amount=prices[data['plan']])]
        )

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def payment_success(message):
    plan = message.successful_payment.invoice_payload.split('_')[1]
    with get_db() as conn:
        conn.execute("UPDATE users SET plan = ? WHERE user_id = ?", (plan, message.chat.id))
    bot.send_message(message.chat.id, f"🎊 Payment Received! You are now a {plan.upper()} member.")

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
