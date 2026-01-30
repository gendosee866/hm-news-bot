import os
import telebot
from telebot import types
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

# Function to get the Telegram token and channel ID
# Accept multiple environment variable names for the token and channel ID
def get_telegram_credentials(token_env_names, channel_env_names):
    token = None
    channel_id = None
    
    for name in token_env_names:
        token = os.getenv(name)
        if token:
            break
    
    for name in channel_env_names:
        channel_id = os.getenv(name)
        if channel_id:
            break
    
    return token, channel_id

# Define your Telegram token and channel ID variable names
# BotHost предоставляет следующие переменные: BOT_TOKEN, API_TOKEN, TELEGRAM_BOT_TOKEN
TOKEN_ENV_NAMES = ["BOT_TOKEN", "API_TOKEN", "TELEGRAM_BOT_TOKEN", "TOKEN"]
CHANNEL_ENV_NAMES = ["CHANNEL_ID", "TELEGRAM_CHANNEL_ID", "TARGET_CHANNEL"]

token, channel_id = get_telegram_credentials(TOKEN_ENV_NAMES, CHANNEL_ENV_NAMES)

# Если токен не найден в переменных окружения, используем запасной
if not token:
    token = "8568785795:AAHFXreBXbUF-ojQk2ARATjbvRxFr1QdCbY"  # Запасной токен

# Если ID канала не указан, попросим админа отправить его боту
if not channel_id:
    print("Warning: Channel ID not found. Please set CHANNEL_ID environment variable.")
    channel_id = None

# Replace with actual admin user IDs
ADMIN_IDS = [1186571866]  # Replace with actual user IDs
# Initialize the bot with the token
bot = telebot.TeleBot(token)

# In-memory storage for users' anonymity choice: user_id -> bool
# True = anonymous, False = not anonymous. If missing -> default False (existing behavior).
anonymous_choice = {}

# Function to check if user is admin
def is_admin(user_id):
    return user_id in ADMIN_IDS

# Command: /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    welcome_text = f"Привет! Я бот для приема новостей для канала ХМ | Главное.\n\n"
    welcome_text += f"Ваш user ID: {user_id}\n\n"
    
    if is_admin(user_id):
        welcome_text += "Вы администратор. Отправьте мне новость, и я перешлю её на канал."
        bot.reply_to(message, welcome_text)
    else:
        welcome_text += "Перед отправкой новости выберите, хотите ли вы отправить её анонимно или нет."
        # Inline keyboard with two buttons
        markup = types.InlineKeyboardMarkup()
        btn_anon = types.InlineKeyboardButton("Анонимно", callback_data="anon_yes")
        btn_not_anon = types.InlineKeyboardButton("Не анонимно", callback_data="anon_no")
        markup.add(btn_anon, btn_not_anon)
        bot.reply_to(message, welcome_text, reply_markup=markup)

# Callback handler for anonymous choice
@bot.callback_query_handler(func=lambda call: call.data in ["anon_yes", "anon_no"])
def anon_choice_callback(call):
    user_id = call.from_user.id
    is_anon = call.data == "anon_yes"
    anonymous_choice[user_id] = is_anon
    # Acknowledge the button press (closes the loading spinner in client)
    bot.answer_callback_query(call.id, "Выбрано: Анонимно" if is_anon else "Выбрано: Не анонимно")
    if is_anon:
        bot.send_message(user_id, "Вы выбрали отправку анонимно. Отправьте, пожалуйста, текст или медиа новости. Информация об авторе не будет передана модераторам.")
    else:
        bot.send_message(user_id, "Вы выбрали отправку не анонимно. Отправьте, пожалуйста, текст или медиа новости. Ваш ник будет указан модераторам.")

# Command: /id to get user ID
@bot.message_handler(commands=['id'])
def send_user_id(message):
    user_id = message.from_user.id
    username = message.from_user.username or "не установлено"
    first_name = message.from_user.first_name or ""
    
    response = f"Ваша информация:\n"
    response += f"User ID: {user_id}\n"
    response += f"Username: @{username}\n"
    response += f"Имя: {first_name}\n"
    response += f"Админ: {'Да' if is_admin(user_id) else 'Нет'}"
    
    bot.reply_to(message, response)

# Command: /setchannel - для установки ID канала (только для админов)
@bot.message_handler(commands=['setchannel'])
def set_channel(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        bot.reply_to(message, "У вас нет прав для выполнения этой команды.")
        return
    
    try:
        # Извлекаем ID канала из сообщения
        channel = message.text.split()[1]
        global channel_id
        channel_id = channel
        bot.reply_to(message, f"ID канала установлен: {channel_id}")
    except IndexError:
        bot.reply_to(message, "Использование: /setchannel @channelname или -100XXXXXXXXX")

# Helper: send message content to admin without forwarding (preserves anonymity)
def send_content_copy_to_admin(admin_id, message, caption=None):
    try:
        ctype = message.content_type
        if ctype == 'text':
            bot.send_message(admin_id, message.text)
        elif ctype == 'photo':
            # send highest resolution photo
            file_id = message.photo[-1].file_id
            # include caption if present
            bot.send_photo(admin_id, file_id, caption=caption or message.caption)
        elif ctype == 'video':
            file_id = message.video.file_id
            bot.send_video(admin_id, file_id, caption=caption or message.caption)
        elif ctype == 'document':
            file_id = message.document.file_id
            bot.send_document(admin_id, file_id, caption=caption or message.caption)
        else:
            # fallback: try forwarding if unknown type (less ideal for anonymity)
            bot.forward_message(admin_id, message.chat.id, message.message_id)
    except Exception as e:
        print(f"Failed to copy content to admin {admin_id}: {e}")

# Handler for text / media messages (news submissions)
@bot.message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_news_submission(message):
    user_id = message.from_user.id
    username = message.from_user.username or "без username"
    first_name = message.from_user.first_name or "Аноним"
    
    if not channel_id:
        bot.reply_to(message, "Ошибка: ID канала не установлен. Администратор должен установить его командой /setchannel")
        return
    
    try:
        # Если пользователь админ, публикуем сразу
        if is_admin(user_id):
            # Пересылаем сообщение на канал
            bot.forward_message(channel_id, message.chat.id, message.message_id)
            bot.reply_to(message, "✅ Новость опубликована на канале!")
        else:
            # Для обычных пользователей - отправляем админам на модерацию
            is_anon = anonymous_choice.get(user_id, False)
            
            if is_anon:
                notification = "📰 Новая новость (анонимно)\n\n"
                # Send notification and copy content to admins without forwarding
                for admin_id in ADMIN_IDS:
                    try:
                        bot.send_message(admin_id, notification)
                        send_content_copy_to_admin(admin_id, message)
                    except Exception as e:
                        print(f"Failed to send anonymous news to admin {admin_id}: {e}")
                bot.reply_to(message, "✅ Ваша новость отправлена на модерацию анонимно. Спасибо!")
            else:
                notification = f"📰 Новая новость от @{username} ({first_name}, ID: {user_id})\n\n"
                for admin_id in ADMIN_IDS:
                    try:
                        bot.send_message(admin_id, notification)
                        bot.forward_message(admin_id, message.chat.id, message.message_id)
                    except Exception as e:
                        print(f"Failed to send to admin {admin_id}: {e}")
                bot.reply_to(message, "✅ Ваша новость отправлена на модерацию. Спасибо!")
            
            # Очистим выбор пользователя (чтобы при следующей отправке он заново выбрал, если нужно)
            if user_id in anonymous_choice:
                del anonymous_choice[user_id]
    
    except Exception as e:
        bot.reply_to(message, f"Ошибка при обработке: {str(e)}")
        print(f"Error: {e}")

# Starting the bot
print("Bot is starting...")
print(f"Token found: {'Yes' if token else 'No'}")
print(f"Channel ID: {channel_id if channel_id else 'Not set'}")
bot.infinity_polling()