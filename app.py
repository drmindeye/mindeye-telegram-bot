from flask import Flask, request
import telebot
import sqlite3
import json
import os
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ---------------- CONFIG ----------------
TOKEN = os.environ.get("TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
PORT = int(os.environ.get("PORT", 5000))

app = Flask(__name__)
bot = telebot.TeleBot(TOKEN, threaded=False)

# ---------------- DATABASE ----------------
conn = sqlite3.connect("subscribers.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    plan TEXT DEFAULT 'free'
)
""")
conn.commit()

# Store admin temporary states safely
admin_state = {}

# ---------------- BOT COMMANDS ----------------
@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(
        message.chat.id,
        "👁️ Welcome to *MindEye Trading AI*\n\n"
        "Use /subscribe to choose a plan.",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=["subscribe"])
def subscribe(message):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🆓 Free", callback_data="sub_free"))
    kb.add(InlineKeyboardButton("💼 Pro ($14.99)", callback_data="sub_pro"))
    kb.add(InlineKeyboardButton("👑 Premium ($29.99)", callback_data="sub_premium"))
    bot.send_message(message.chat.id, "Choose your plan:", reply_markup=kb)

# ---------------- SUBSCRIPTION HANDLER ----------------
@bot.callback_query_handler(func=lambda c: c.data.startswith("sub_"))
def handle_sub(c):
    plan = c.data.split("_")[1]
    cursor.execute(
        "INSERT OR REPLACE INTO users (user_id, plan) VALUES (?, ?)",
        (c.from_user.id, plan)
    )
    conn.commit()
    bot.answer_callback_query(c.id, f"Subscribed to {plan.upper()}")
    bot.send_message(
        c.message.chat.id,
        f"✅ You are now on *{plan.upper()}* plan.\nSignals will be sent here.",
        parse_mode="Markdown"
    )

# ---------------- ADMIN SEND ----------------
@bot.message_handler(commands=["send"])
def admin_send(message):
    if message.from_user.id != ADMIN_ID:
        return
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("Free", callback_data="send_free"))
    kb.add(InlineKeyboardButton("Pro", callback_data="send_pro"))
    kb.add(InlineKeyboardButton("Premium", callback_data="send_premium"))
    kb.add(InlineKeyboardButton("All", callback_data="send_all"))
    bot.send_message(message.chat.id, "Send signal to:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("send_"))
def set_target(c):
    if c.from_user.id != ADMIN_ID:
        return
    admin_state[c.from_user.id] = c.data.split("_")[1]
    bot.answer_callback_query(c.id)
    bot.send_message(c.message.chat.id, "✍️ Send the signal text now:")

@bot.message_handler(func=lambda m: True)
def broadcast(message):
    if message.from_user.id != ADMIN_ID:
        return

    target = admin_state.get(message.from_user.id)
    if not target:
        return

    if target == "all":
        cursor.execute("SELECT user_id FROM users")
    else:
        cursor.execute("SELECT user_id FROM users WHERE plan = ?", (target,))

    users = cursor.fetchall()
    sent = 0

    for u in users:
        try:
            bot.send_message(u[0], message.text)
            sent += 1
        except:
            pass

    bot.send_message(message.chat.id, f"✅ Sent to {sent} users")
    admin_state.pop(message.from_user.id, None)

# ---------------- MINI APP DATA ----------------
@bot.message_handler(content_types=["web_app_data"])
def handle_web_app(message):
    data = json.loads(message.web_app_data.data)

    if data["action"] == "subscribe":
        cursor.execute(
            "INSERT OR REPLACE INTO users (user_id, plan) VALUES (?, ?)",
            (data["userId"], data["plan"])
        )
        conn.commit()
        bot.send_message(
            data["userId"],
            f"🎉 Subscription activated: *{data['plan'].upper()}*",
            parse_mode="Markdown"
        )

# ---------------- WEBHOOK ----------------
@app.route("/webhook", methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(
        request.stream.read().decode("utf-8")
    )
    bot.process_new_updates([update])
    return "OK", 200

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
