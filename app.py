from flask import Flask, request
import telebot
import sqlite3
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import json

app = Flask(__name__)

import os
TOKEN = os.environ.get('TOKEN')  # From env vars
ADMIN_ID = int(os.environ.get('ADMIN_ID'))

bot = telebot.TeleBot(TOKEN, threaded=False)

# DB setup
conn = sqlite3.connect('subscribers.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                  (user_id INTEGER PRIMARY KEY, plan TEXT DEFAULT 'free')''')
conn.commit()

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Welcome to MindEye Trading Bot! Use /subscribe to join.")

@bot.message_handler(commands=['subscribe'])
def subscribe(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Free", callback_data='sub_free'))
    markup.add(InlineKeyboardButton("Pro ($14.99)", callback_data='sub_pro'))
    markup.add(InlineKeyboardButton("Premium ($29.99)", callback_data='sub_premium'))
    bot.reply_to(message, "Choose your plan:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('sub_'))
def handle_sub(call):
    plan = call.data.split('_')[1]
    cursor.execute("INSERT OR REPLACE INTO users (user_id, plan) VALUES (?, ?)", (call.from_user.id, plan))
    conn.commit()
    bot.answer_callback_query(call.id, f"Subscribed to {plan.capitalize()} plan!")
    bot.send_message(call.message.chat.id, f"You're now on the {plan} plan. Signals will be sent here.")

# Admin send signal
@bot.message_handler(commands=['send'])
def send_signal(message):
    if message.from_user.id != ADMIN_ID:
        return
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Free", callback_data='send_free'))
    markup.add(InlineKeyboardButton("Pro", callback_data='send_pro'))
    markup.add(InlineKeyboardButton("Premium", callback_data='send_premium'))
    markup.add(InlineKeyboardButton("All", callback_data='send_all'))
    bot.reply_to(message, "Choose group:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('send_'))
def handle_send(call):
    global target_group
    target_group = call.data.split('_')[1]
    bot.answer_callback_query(call.id, f"Sending to {target_group} users.")
    bot.send_message(call.message.chat.id, "Enter the signal text:")

@bot.message_handler(func=lambda m: True)  # After callback
def broadcast(message):
    if message.from_user.id != ADMIN_ID:
        return
    cursor.execute("SELECT user_id FROM users WHERE plan = ? OR ? = 'all'", (target_group, target_group))
    users = cursor.fetchall()
    for user in users:
        try:
            bot.send_message(user[0], message.text)
        except:
            pass
    bot.reply_to(message, f"Sent to {len(users)} users!")

# Mini App data
@bot.message_handler(content_types=['web_app_data'])
def handle_web_data(message):
    data = json.loads(message.web_app_data.data)
    if data['action'] == 'subscribe':
        cursor.execute("INSERT OR REPLACE INTO users (user_id, plan) VALUES (?, ?)", (data['userId'], data['plan']))
        conn.commit()
        bot.send_message(data['userId'], f"Subscribed to {data['plan']}! Signals incoming.")
    elif data['action'] == 'buy_stars':
        prices = {'pro': 1499, 'premium': 2999}
        bot.send_invoice(
            chat_id=message.chat.id,
            title=f"{data['plan'].capitalize()} Plan",
            description="Premium signals",
            payload=f"plan_{data['plan']}",
            currency="XTR",
            prices=[telebot.types.LabeledPrice("Plan", prices[data['plan']])]
        )

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    payload = message.successful_payment.invoice_payload
    plan = payload.split('_')[1]
    cursor.execute("UPDATE users SET plan = ? WHERE user_id = ?", (plan, message.chat.id))
    conn.commit()
    bot.send_message(message.chat.id, f"Thanks! Now on {plan}. Signals here.")

@app.route('/webhook', methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
    bot.process_new_updates([update])
    return 'ok', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
