from flask import Flask, request
import telebot
import sqlite3
import json
import os
import threading
import time
from datetime import datetime, timedelta
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

# Initialize Database with Expiry Support
with get_db() as conn:
    conn.execute('''CREATE TABLE IF NOT EXISTS users 
                  (user_id INTEGER PRIMARY KEY, 
                   plan TEXT DEFAULT 'free', 
                   expiry_date TEXT)''')

# --- BACKGROUND TASK: AUTOMATIC DEACTIVATION ---
def check_expirations():
    while True:
        try:
            now = datetime.now()
            with get_db() as conn:
                cursor = conn.cursor()
                # Find users whose expiry date has passed and aren't already 'expired'
                cursor.execute("SELECT user_id FROM users WHERE expiry_date < ? AND plan != 'expired'", (now.isoformat(),))
                expired_users = cursor.fetchall()
                
                for (u_id,) in expired_users:
                    conn.execute("UPDATE users SET plan = 'expired' WHERE user_id = ?", (u_id,))
                    try:
                        bot.send_message(u_id, "⚠️ <b>Subscription Expired</b>\nYour access has ended. Visit the Mini App to renew!")
                    except: pass
                conn.commit()
        except Exception as e:
            print(f"Cleanup Error: {e}")
        time.sleep(86400) # Run once every 24 hours

# Start the background thread
threading.Thread(target=check_expirations, daemon=True).start()

# --- 1. USER COMMANDS ---

@bot.message_handler(commands=['start'])
def start(message):
    welcome_text = (
        f"<b>Welcome to MindEye AI Analyst!</b> 🚀\n\n"
        "To access our trading signals and mentorship, "
        "please click the <b>'Signals'</b> button at the bottom left."
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="HTML")

@bot.message_handler(commands=['id'])
def get_id(m):
    bot.reply_to(m, f"🆔 Your MindEye ID: <code>{m.from_user.id}</code>", parse_mode="HTML")

# --- 2. ADMIN: UPGRADE & PHOTO BROADCASTING ---

@bot.message_handler(commands=['upgrade'])
def manual_upgrade(m):
    if str(m.from_user.id) != str(ADMIN_ID): return
    try:
        args = m.text.split()
        user_id, plan = args[1], args[2]
        expiry = (datetime.now() + timedelta(days=30)).isoformat()
        
        with get_db() as conn:
            conn.execute("INSERT OR REPLACE INTO users (user_id, plan, expiry_date) VALUES (?, ?, ?)", (user_id, plan, expiry))
        
        bot.send_message(m.chat.id, f"✅ {user_id} upgraded to {plan.upper()} (Expires in 30 days).")
        bot.send_message(user_id, f"🌟 <b>Membership Activated!</b>\nYour {plan.upper()} access is live for 30 days.")
    except:
        bot.reply_to(m, "Usage: /upgrade [ID] [pro/premium]")

@bot.message_handler(commands=['send'])
def admin_broadcast_start(message):
    if str(message.from_user.id) != str(ADMIN_ID): return
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Free", callback_data='send_free'), 
               InlineKeyboardButton("Pro", callback_data='send_pro'))
    markup.add(InlineKeyboardButton("Premium", callback_data='send_premium'), 
               InlineKeyboardButton("All", callback_data='send_all'))
    bot.reply_to(message, "📢 Select target for signal (Text or Photo):", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('send_'))
def set_broadcast_target(call):
    target = call.data.split('_')[1]
    admin_states[call.from_user.id] = target
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, f"🎯 Target: {target.upper()}\nSend your message or photo now:")

@bot.message_handler(content_types=['text', 'photo'], func=lambda m: m.from_user.id in admin_states)
def perform_broadcast(message):
    target = admin_states.pop(message.from_user.id)
    with get_db() as conn:
        cursor = conn.cursor()
        if target == 'all': cursor.execute("SELECT user_id FROM users WHERE plan != 'expired'")
        else: cursor.execute("SELECT user_id FROM users WHERE plan = ?", (target,))
        users = cursor.fetchall()
    
    count = 0
    for (u_id,) in users:
        try:
            bot.copy_message(u_id, message.chat.id, message.message_id)
            count += 1
        except: continue
    bot.reply_to(message, f"✅ Sent to {count} users.")

# --- 3. MINI APP DATA ---

@bot.message_handler(content_types=['web_app_data'])
def handle_app_data(message):
    try:
        data = json.loads(message.web_app_data.data)
        user_id = message.from_user.id
        expiry = (datetime.now() + timedelta(days=30)).isoformat()
        
        if data['action'] == 'subscribe':
            with get_db() as conn:
                conn.execute("INSERT OR REPLACE INTO users (user_id, plan, expiry_date) VALUES (?, 'free', ?)", (user_id, expiry))
            bot.send_message(user_id, "✅ <b>Free Plan Activated!</b>\nYou're registered for 30 days.")
            
        elif data['action'] == 'buy_stars':
            prices = {'pro': 555, 'premium': 1111}
            bot.send_invoice(user_id, f"MindEye {data['plan'].capitalize()}", "1-Month Access", f"plan_{data['plan']}", "", "XTR", [LabeledPrice("Price", prices[data['plan']])])
    except: pass

@bot.pre_checkout_query_handler(func=lambda q: True)
def checkout(q): bot.answer_pre_checkout_query(q.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def success(m):
    plan = m.successful_payment.invoice_payload.split('_')[1]
    expiry = (datetime.now() + timedelta(days=30)).isoformat()
    with get_db() as conn:
        conn.execute("UPDATE users SET plan = ?, expiry_date = ? WHERE user_id = ?", (plan, expiry, m.chat.id))
    bot.send_message(m.chat.id, "🌟 <b>Payment Successful!</b> Your access is now live.")

@app.route('/webhook', methods=['POST'])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return '', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
