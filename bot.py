import os
import telebot
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

if not token:
    raise ValueError("Missing Telegram token in environment variables.")

# Если ID канала не указан, попросим админа отправить его боту
if not channel_id:
    print("Warning: Channel ID not found. Please set CHANNEL_ID environment variable.")
    channel_id = None

# Replace with actual admin user IDs
ADMIN_IDS = [123456789, 987654321]  # Replace with actual user IDs

# Initialize the bot with the token
bot = telebot.TeleBot(token)

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
    else:
        welcome_text += "Отправьте мне вашу новость для публикации. Она будет проверена модератором."
    
    bot.reply_to(message, welcome_text)

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

# Handler for text messages (news submissions)
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
            notification = f"📰 Новая новость от @{username} ({first_name}, ID: {user_id})\n\n"
            
            for admin_id in ADMIN_IDS:
                try:
                    bot.send_message(admin_id, notification)
                    bot.forward_message(admin_id, message.chat.id, message.message_id)
                except Exception as e:
                    print(f"Failed to send to admin {admin_id}: {e}")
            
            bot.reply_to(message, "✅ Ваша новость отправлена на модерацию. Спасибо!")
    
    except Exception as e:
        bot.reply_to(message, f"Ошибка при обработке: {str(e)}")
        print(f"Error: {e}")

# Starting the bot
print("Bot is starting...")
print(f"Token found: {'Yes' if token else 'No'}")
print(f"Channel ID: {channel_id if channel_id else 'Not set'}")
bot.infinity_polling()
