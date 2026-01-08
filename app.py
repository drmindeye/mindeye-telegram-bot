from flask import Flask, request, jsonify # Added jsonify
import telebot
import sqlite3
import json
import os
import threading
import time
from datetime import datetime, timedelta
from telebot.types import LabeledPrice, InlineKeyboardMarkup, InlineKeyboardButton

app = Flask(__name__)
TOKEN = os.environ.get('TOKEN')
ADMIN_ID = os.environ.get('ADMIN_ID')

bot = telebot.TeleBot(TOKEN, threaded=False)
admin_states = {}

def get_db():
    conn = sqlite3.connect('subscribers.db', check_same_thread=False)
    return conn

with get_db() as conn:
    conn.execute('''CREATE TABLE IF NOT EXISTS users 
                  (user_id INTEGER PRIMARY KEY, plan TEXT, expiry TEXT)''')

# --- NEW: STATUS API FOR MINI APP ---
@app.route('/status/<int:user_id>', methods=['GET'])
def get_status(user_id):
    with get_db() as conn:
        user = conn.execute("SELECT plan, expiry FROM users WHERE user_id = ?", (user_id,)).fetchone()
    
    if user and user[1]:
        expiry_date = datetime.fromisoformat(user[1])
        remaining = (expiry_date - datetime.now()).days
        return jsonify({"plan": user[0], "days_left": max(0, remaining)})
    return jsonify({"plan": "none", "days_left": 0})

# --- BACKGROUND TASK: DEACTIVATION ---
def cleanup_expired_users():
    while True:
        try:
            now = datetime.now().isoformat()
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id FROM users WHERE expiry < ? AND plan != 'expired'", (now,))
                expired = cursor.fetchall()
                for (uid,) in expired:
                    conn.execute("UPDATE users SET plan = 'expired' WHERE user_id = ?", (uid,))
                    try:
                        bot.send_message(uid, "⚠️ <b>Access Expired</b>\nYour subscription has ended. Renew in the Mini App!")
                    except: pass
                conn.commit()
        except: pass
        time.sleep(86400)

threading.Thread(target=cleanup_expired_users, daemon=True).start()

# --- WEB APP DATA (FREE & STARS) ---
@bot.message_handler(content_types=['web_app_data'])
def handle_app_data(message):
    try:
        data = json.loads(message.web_app_data.data)
        user_id = message.from_user.id
        expiry = (datetime.now() + timedelta(days=30)).isoformat()
        
        if data['action'] == 'subscribe':
            with get_db() as conn:
                conn.execute("INSERT OR REPLACE INTO users (user_id, plan, expiry) VALUES (?, 'free', ?)", (user_id, expiry))
            bot.send_message(user_id, "✅ <b>Free Plan Active!</b>\n30 days access granted.", parse_mode="HTML")
            
        elif data['action'] == 'buy_stars':
            prices = {'pro': 555, 'premium': 1111}
            bot.send_invoice(user_id, f"MindEye {data['plan'].capitalize()}", "1-Month Access", f"plan_{data['plan']}", "", "XTR", [LabeledPrice("Price", prices[data['plan']])])
    except: pass

# --- ADMIN BROADCAST (PHOTOS SUPPORTED) ---
@bot.message_handler(commands=['send'])
def broadcast_cmd(m):
    if str(m.from_user.id) != str(ADMIN_ID): return
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("All Active", callback_data="send_all"))
    bot.reply_to(m, "Broadcast target:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('send_'))
def handle_target(call):
    admin_states[call.from_user.id] = call.data.split('_')[1]
    bot.send_message(call.message.chat.id, "Send Signal (Text/Photo):")

@bot.message_handler(content_types=['text', 'photo'], func=lambda m: m.from_user.id in admin_states)
def run_broadcast(m):
    admin_states.pop(m.from_user.id)
    with get_db() as conn:
        users = conn.execute("SELECT user_id FROM users WHERE plan != 'expired'").fetchall()
    for (uid,) in users:
        try: bot.copy_message(uid, m.chat.id, m.message_id)
        except: continue
    bot.reply_to(m, "✅ Sent!")

# --- BASIC COMMANDS ---
@bot.message_handler(commands=['start'])
def start(m): bot.send_message(m.chat.id, "Welcome to MindEye AI Analyst! Click the menu button to start.")

@bot.message_handler(commands=['id'])
def show_id(m): bot.reply_to(m, f"🆔 ID: <code>{m.from_user.id}</code>", parse_mode="HTML")

@bot.message_handler(commands=['upgrade'])
def manual(m):
    if str(m.from_user.id) != str(ADMIN_ID): return
    args = m.text.split()
    exp = (datetime.now() + timedelta(days=30)).isoformat()
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO users (user_id, plan, expiry) VALUES (?, ?, ?)", (args[1], args[2], exp))
    bot.send_message(args[1], "🌟 Membership Active!")

@app.route('/webhook', methods=['POST'])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return '', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
from flask import Flask, request, jsonify # Added jsonify
import telebot
import sqlite3
import json
import os
import threading
import time
from datetime import datetime, timedelta
from telebot.types import LabeledPrice, InlineKeyboardMarkup, InlineKeyboardButton

app = Flask(__name__)
TOKEN = os.environ.get('TOKEN')
ADMIN_ID = os.environ.get('ADMIN_ID')

bot = telebot.TeleBot(TOKEN, threaded=False)
admin_states = {}

def get_db():
    conn = sqlite3.connect('subscribers.db', check_same_thread=False)
    return conn

with get_db() as conn:
    conn.execute('''CREATE TABLE IF NOT EXISTS users 
                  (user_id INTEGER PRIMARY KEY, plan TEXT, expiry TEXT)''')

# --- NEW: STATUS API FOR MINI APP ---
@app.route('/status/<int:user_id>', methods=['GET'])
def get_status(user_id):
    with get_db() as conn:
        user = conn.execute("SELECT plan, expiry FROM users WHERE user_id = ?", (user_id,)).fetchone()
    
    if user and user[1]:
        expiry_date = datetime.fromisoformat(user[1])
        remaining = (expiry_date - datetime.now()).days
        return jsonify({"plan": user[0], "days_left": max(0, remaining)})
    return jsonify({"plan": "none", "days_left": 0})

# --- BACKGROUND TASK: DEACTIVATION ---
def cleanup_expired_users():
    while True:
        try:
            now = datetime.now().isoformat()
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id FROM users WHERE expiry < ? AND plan != 'expired'", (now,))
                expired = cursor.fetchall()
                for (uid,) in expired:
                    conn.execute("UPDATE users SET plan = 'expired' WHERE user_id = ?", (uid,))
                    try:
                        bot.send_message(uid, "⚠️ <b>Access Expired</b>\nYour subscription has ended. Renew in the Mini App!")
                    except: pass
                conn.commit()
        except: pass
        time.sleep(86400)

threading.Thread(target=cleanup_expired_users, daemon=True).start()

# --- WEB APP DATA (FREE & STARS) ---
@bot.message_handler(content_types=['web_app_data'])
def handle_app_data(message):
    try:
        data = json.loads(message.web_app_data.data)
        user_id = message.from_user.id
        expiry = (datetime.now() + timedelta(days=30)).isoformat()
        
        if data['action'] == 'subscribe':
            with get_db() as conn:
                conn.execute("INSERT OR REPLACE INTO users (user_id, plan, expiry) VALUES (?, 'free', ?)", (user_id, expiry))
            bot.send_message(user_id, "✅ <b>Free Plan Active!</b>\n30 days access granted.", parse_mode="HTML")
            
        elif data['action'] == 'buy_stars':
            prices = {'pro': 555, 'premium': 1111}
            bot.send_invoice(user_id, f"MindEye {data['plan'].capitalize()}", "1-Month Access", f"plan_{data['plan']}", "", "XTR", [LabeledPrice("Price", prices[data['plan']])])
    except: pass

# --- ADMIN BROADCAST (PHOTOS SUPPORTED) ---
@bot.message_handler(commands=['send'])
def broadcast_cmd(m):
    if str(m.from_user.id) != str(ADMIN_ID): return
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("All Active", callback_data="send_all"))
    bot.reply_to(m, "Broadcast target:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('send_'))
def handle_target(call):
    admin_states[call.from_user.id] = call.data.split('_')[1]
    bot.send_message(call.message.chat.id, "Send Signal (Text/Photo):")

@bot.message_handler(content_types=['text', 'photo'], func=lambda m: m.from_user.id in admin_states)
def run_broadcast(m):
    admin_states.pop(m.from_user.id)
    with get_db() as conn:
        users = conn.execute("SELECT user_id FROM users WHERE plan != 'expired'").fetchall()
    for (uid,) in users:
        try: bot.copy_message(uid, m.chat.id, m.message_id)
        except: continue
    bot.reply_to(m, "✅ Sent!")

# --- BASIC COMMANDS ---
@bot.message_handler(commands=['start'])
def start(m): bot.send_message(m.chat.id, "Welcome to MindEye AI Analyst! Click the menu button to start.")

@bot.message_handler(commands=['id'])
def show_id(m): bot.reply_to(m, f"🆔 ID: <code>{m.from_user.id}</code>", parse_mode="HTML")

@bot.message_handler(commands=['upgrade'])
def manual(m):
    if str(m.from_user.id) != str(ADMIN_ID): return
    args = m.text.split()
    exp = (datetime.now() + timedelta(days=30)).isoformat()
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO users (user_id, plan, expiry) VALUES (?, ?, ?)", (args[1], args[2], exp))
    bot.send_message(args[1], "🌟 Membership Active!")

@app.route('/webhook', methods=['POST'])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return '', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
