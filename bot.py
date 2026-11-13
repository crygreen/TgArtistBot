import os
import sqlite3
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# 1. Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = os.getenv('ADMIN_ID')

if not BOT_TOKEN or not ADMIN_ID:
    print("🚨 Ошибка: Не найдены BOT_TOKEN или ADMIN_ID")
    exit(1)

bot = telebot.TeleBot(BOT_TOKEN)

# 2. Database setup
conn = sqlite3.connect('bot_database.db', check_same_thread=False)
cursor = conn.cursor()
db_lock = threading.Lock() # 🚨 ДОБАВЛЕНА БЛОКИРОВКА ДЛЯ БАЗЫ

# Create tables
with db_lock:
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            content TEXT,
            is_anonymous BOOLEAN,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            admin_message_id INTEGER PRIMARY KEY,
            user_id INTEGER
        )
    ''')
    conn.commit()

# 3. Handlers

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username or "No_username"
    
    with db_lock: # 🚨 БЛОКИРОВКА
        cursor.execute("INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)", (user_id, username))
        conn.commit()

    welcome_text = (
        f"Салют, {message.from_user.first_name}! 👋\n"
        "Сюда ты можешь отправить свои предложения, мемчик, с которого тебя разрывает, или просто послать меня нахуй."
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(content_types=['text', 'photo', 'video'])
def handle_content(message):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🕵️ Анонимно", callback_data="anon_yes"),
        InlineKeyboardButton("👤 С моим ником", callback_data="anon_no")
    )
    bot.reply_to(message, "как отправим?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('anon_'))
def handle_anonymity(call):
    is_anonymous = True if call.data == "anon_yes" else False
    user_id = call.from_user.id
    message = call.message.reply_to_message

    if not message:
        bot.answer_callback_query(call.id, "Ошибка: сообщение не найдено.")
        return

    content_type = message.content_type
    content_data = message.text if content_type == 'text' else message.caption or ""
    
    with db_lock: # 🚨 БЛОКИРОВКА
        cursor.execute(
            "INSERT INTO ideas (user_id, content, is_anonymous) VALUES (?, ?, ?)",
            (user_id, content_data, is_anonymous)
        )
        conn.commit()

    if is_anonymous:
        admin_text = "🕵️ **Анонимная идея:**\n\n"
    else:
        username = f"@{call.from_user.username}" if call.from_user.username else call.from_user.first_name
        admin_text = f"👤 **Идея от {username}:**\n\n"

    sent_message = None
    
    if content_type == 'text':
        sent_message = bot.send_message(ADMIN_ID, admin_text + message.text, parse_mode='Markdown')
    else:
        sent_message = bot.copy_message(chat_id=ADMIN_ID, from_chat_id=message.chat.id, message_id=message.message_id, caption=admin_text)

    if sent_message:
        with db_lock: # 🚨 БЛОКИРОВКА
            cursor.execute(
                "INSERT INTO tickets (admin_message_id, user_id) VALUES (?, ?)",
                (sent_message.message_id, user_id)
            )
            conn.commit()

    bot.edit_message_text(
        chat_id=call.message.chat.id, 
        message_id=call.message.message_id, 
        text="сообщение отправлено, спасибо за обратную связь, чуви"
    )

@bot.message_handler(commands=['reply'])
def reply_to_user(message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return

    if message.reply_to_message:
        admin_msg_id = message.reply_to_message.message_id
        
        with db_lock: # 🚨 БЛОКИРОВКА
            cursor.execute("SELECT user_id FROM tickets WHERE admin_message_id = ?", (admin_msg_id,))
            result = cursor.fetchone()
        
        if result:
            user_id = result[0]
            reply_text = message.text.replace('/reply', '').strip()
            
            if reply_text:
                try:
                    bot.send_message(user_id, f"Ответ от crygreen:\n\n{reply_text}")
                    bot.reply_to(message, "✅ Ответ отправлен!")
                except Exception:
                    bot.reply_to(message, "❌ Ошибка: пользователь заблокировал бота.")
            else:
                bot.reply_to(message, "⚠️ Напиши текст после команды. Например: /reply Спасибо!")
        else:
            bot.reply_to(message, "⚠️ Не могу найти автора этого сообщения.")
    else:
        bot.reply_to(message, "⚠️ Чтобы ответить, зажми сообщение и выбери 'Reply', затем напиши /reply Твой текст")

# --- Заглушка для Render (с поддержкой HEAD запросов) ---
class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

    def do_HEAD(self): # 🚨 ДОБАВЛЕНО ДЛЯ RENDER
        self.send_response(200)
        self.end_headers()

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), DummyServer)
    server.serve_forever()

threading.Thread(target=run_dummy_server, daemon=True).start()
# -------------------------------------------------------

print("Bot is running... (Бот запущен...)")
bot.polling(none_stop=True)