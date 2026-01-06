from flask import Flask, request
import telebot
import sqlite3
import json
import os
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice

app = Flask(__name__)

# --- CONFIGURATION ---
TOKEN = os.environ.get('TOKEN')
ADMIN_ID = os.environ.get('ADMIN_ID')
PAYMENT_TOKEN = os.environ.get('PAYMENT_TOKEN', '') 

bot = telebot.TeleBot(TOKEN, threaded=False)
admin_states = {}

def get_db():
    conn = sqlite3.connect('subscribers.db', check_same_thread=False)
    return conn

# Initialize Database
with get_db() as conn:
    conn.execute('''CREATE TABLE IF NOT EXISTS users 
                  (user_id INTEGER PRIMARY KEY, plan TEXT DEFAULT 'free')''')

# --- 1. USER COMMANDS ---

@bot.message_handler(commands=['start'])
def start(message):
    welcome_text = (
        f"<b>Welcome, {message.from_user.first_name}!</b> 🚀\n\n"
        "To access our trading signals and mentorship, "
        "please click the <b>'Signals'</b> button at the bottom left.\n\n"
        "<i>Note: If you are paying via Crypto/Fiat, use /id to get your number.</i>"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="HTML")

@bot.message_handler(commands=['id'])
def get_user_id(message):
    """Separate command for users to get their ID for manual payments"""
    user_id = message.from_user.id
    response = (
        f"🆔 <b>Your MindEye ID:</b>\n\n"
        f"<code>{user_id}</code>\n\n"
        f"<i>(Tap the number above to copy it)</i>\n"
        f"Please provide this ID to support for manual onboarding."
    )
    bot.send_message(message.chat.id, response, parse_mode="HTML")

# --- 2. ADMIN COMMANDS (UPGRADE & BROADCAST) ---

@bot.message_handler(commands=['upgrade'])
def manual_upgrade(message):
    """Admin tool to manually upgrade a user: /upgrade [ID] [plan]"""
    if str(message.from_user.id) != str(ADMIN_ID): return
    try:
        args = message.text.split()
        target_id = args[1]
        new_plan = args[2].lower() # pro or premium
        
        with get_db() as conn:
            conn.execute("INSERT OR REPLACE INTO users (user_id, plan) VALUES (?, ?)", (target_id, new_plan))
        
        bot.send_message(message.chat.id, f"✅ Success: {target_id} upgraded to {new_plan.upper()}.")
        bot.send_message(target_id, f"🌟 <b>Membership Active!</b>\nYour {new_plan.upper()} plan has been activated. Welcome!")
    except:
        bot.reply_to(message, "❌ Use: /upgrade [USER_ID] [pro/premium]")

@bot.message_handler(commands=['send'])
def admin_broadcast_start(message):
    if str(message.from_user.id) != str(ADMIN_ID): return
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Free", callback_data='send_free'), 
               InlineKeyboardButton("Pro", callback_data='send_pro'))
    markup.add(InlineKeyboardButton("Premium", callback_data='send_premium'), 
               InlineKeyboardButton("All", callback_data='send_all'))
    bot.reply_to(message, "📢 Select target group for the signal:", reply_markup=markup)

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
        if target == 'all': cursor.execute("SELECT user_id FROM users")
        else: cursor.execute("SELECT user_id FROM users WHERE plan = ?", (target,))
        users = cursor.fetchall()
    
    count = 0
    for u in users:
        try:
            bot.copy_message(u[0], message.chat.id, message.message_id)
            count += 1
        except: continue
    bot.reply_to(message, f"✅ Signal sent to {count} users.")

# --- 3. MINI APP DATA & PAYMENTS ---

@bot.message_handler(content_types=['web_app_data'])
def handle_app_data(message):
    data = json.loads(message.web_app_data.data)
    user_id = message.from_user.id
    
    if data['action'] == 'subscribe':
        with get_db() as conn:
            conn.execute("INSERT OR REPLACE INTO users (user_id, plan) VALUES (?, ?)", (user_id, 'free'))
        bot.send_message(user_id, "✅ <b>Registered!</b>\nYour 1-Month Free Plan is active.")
    
    elif data['action'] == 'buy_stars':
        currency = "USD" if PAYMENT_TOKEN else "XTR"
        prices_map = {'pro': 1499 if PAYMENT_TOKEN else 555, 
                      'premium': 2999 if PAYMENT_TOKEN else 1111}
        bot.send_invoice(user_id, f"MindEye {data['plan'].capitalize()}", "1-Month Access", f"plan_{data['plan']}", PAYMENT_TOKEN, currency, [LabeledPrice("Fee", prices_map[data['plan']])])

@bot.pre_checkout_query_handler(func=lambda q: True)
def checkout_ok(q): bot.answer_pre_checkout_query(q.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def payment_success(message):
    plan = message.successful_payment.invoice_payload.split('_')[1]
    with get_db() as conn:
        conn.execute("UPDATE users SET plan = ? WHERE user_id = ?", (plan, message.chat.id))
    bot.send_message(message.chat.id, f"🌟 <b>Success!</b>\nYou are now a {plan.upper()} member.")

# --- 4. DEPLOYMENT ---

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
        return ''
    return 'Forbidden', 403

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
