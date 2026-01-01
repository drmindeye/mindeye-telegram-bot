from flask import Flask, request
import telebot
import sqlite3
import json
import os
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, WebAppInfo

app = Flask(__name__)

# --- CONFIGURATION ---
TOKEN = os.environ.get('TOKEN')
ADMIN_ID = os.environ.get('ADMIN_ID')
# If you connect Stripe/PayPal in BotFather, add the token to Render as PAYMENT_TOKEN
PAYMENT_TOKEN = os.environ.get('PAYMENT_TOKEN', '') 
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

# --- 1. WELCOME MESSAGE ---
@bot.message_handler(commands=['start'])
def start(message):
    welcome_text = (
        "<b>Welcome to MindEye AI Analyst!</b> 🚀\n\n"
        "To access our trading signals, mentorship, and AI bots, "
        "please click the <b>'MINDEYE AI'</b> button located at the bottom left "
        "of your screen (next to the keyboard).\n\n"
        "<i>Note: Opening the app via the 'MINDEYE AI' menu button ensures all features work correctly.</i>"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="HTML")

# --- 2. ADMIN SIGNAL BROADCASTING ---
@bot.message_handler(commands=['send'])
def admin_broadcast_start(message):
    if str(message.from_user.id) != str(ADMIN_ID):
        bot.reply_to(message, "❌ Access Denied.")
        return
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Free", callback_data='send_free'), InlineKeyboardButton("Pro", callback_data='send_pro'))
    markup.add(InlineKeyboardButton("Premium", callback_data='send_premium'), InlineKeyboardButton("All", callback_data='send_all'))
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

# --- 3. MINI APP DATA & PAYMENTS ---
@bot.message_handler(content_types=['web_app_data'])
def handle_app_data(message):
    data = json.loads(message.web_app_data.data)
    user_id = message.from_user.id
    
    if data['action'] == 'subscribe':
        with get_db() as conn:
            conn.execute("INSERT OR REPLACE INTO users (user_id, plan) VALUES (?, ?)", (user_id, 'free'))
        bot.send_message(user_id, "✅ <b>Registered!</b>\nYour 1-Month Free Plan is now active. Watch this chat for signals!")

    elif data['action'] == 'buy_stars':
        # If PAYMENT_TOKEN is provided, use USD. Otherwise, use Telegram Stars (XTR).
        if PAYMENT_TOKEN:
            currency = "USD"
            # Prices in cents (1499 = $14.99)
            prices_map = {'pro': 1499, 'premium': 2999} 
        else:
            currency = "XTR"
            # Prices in Stars
            prices_map = {'pro': 555, 'premium': 1111}

        bot.send_invoice(
            chat_id=user_id,
            title=f"MindEye {data['plan'].capitalize()} Plan",
            description=f"1-Month subscription for {data['plan']} signals.",
            payload=f"plan_{data['plan']}",
            provider_token=PAYMENT_TOKEN, 
            currency=currency, 
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
    bot.send_message(message.chat.id, f"🌟 <b>Payment Confirmed!</b>\nYou are now a {plan.upper()} member. Welcome to the elite group!")

# --- 4. WEBHOOK ROUTE ---
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
