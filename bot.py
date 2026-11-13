import os
import sqlite3
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

# 1. Load environment variables (Загружаем переменные окружения)
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = os.getenv('ADMIN_ID')

bot = telebot.TeleBot(BOT_TOKEN)

# 2. Database setup (Настройка базы данных)
conn = sqlite3.connect('bot_database.db', check_same_thread=False)
cursor = conn.cursor()

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
conn.commit()

# 3. Handlers (Обработчики)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username or "No_username"
    
    # Save user to database
    cursor.execute("INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()

    # UPDATED welcome text (Обновленный текст)
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
    
    # UPDATED question text (Обновленный вопрос)
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
    
    # Save to DB
    cursor.execute(
        "INSERT INTO ideas (user_id, content, is_anonymous) VALUES (?, ?, ?)",
        (user_id, content_data, is_anonymous)
    )
    conn.commit()

    # Send to Admin
    if is_anonymous:
        admin_text = "🕵️ **Анонимная идея:**\n\n"
    else:
        username = f"@{call.from_user.username}" if call.from_user.username else call.from_user.first_name
        admin_text = f"👤 **Идея от {username}:**\n\n"

    if content_type == 'text':
        bot.send_message(ADMIN_ID, admin_text + message.text, parse_mode='Markdown')
    else:
        bot.copy_message(chat_id=ADMIN_ID, from_chat_id=message.chat.id, message_id=message.message_id, caption=admin_text)

    # UPDATED confirmation text (Обновленный текст подтверждения)
    bot.edit_message_text(
        chat_id=call.message.chat.id, 
        message_id=call.message.message_id, 
        text="сообщение отправлено, спасибо за обратную связь, чуви"
    )

# 4. Start polling (Запускаем бота)
print("Bot is running... (Бот запущен...)")
bot.polling(none_stop=True)