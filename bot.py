import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# Optionally load from a .env file:
# from dotenv import load_dotenv
# load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

## Get environment variables
BOT_TOKEN = os.getenv('BOT_TOKEN')  # ожидает переменную окружения BOT_TOKEN
CHANNEL_ID = os.getenv('@hm_glavnoe')  # замените на ваш канал или оставьте @hm_glavnoe по умолчанию
# ADMIN_IDS может содержать через запятую id админов (например "12345,67890") и/или юзернеймы (@aksarin86)
ADMIN_IDS = [a.strip() for a in os.getenv('ADMIN_IDS', '@aksarin86').split(',') if a.strip()]

# Storage for pending news (in production use database)
pending_news = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        'Привет! Я бот для приёма предложенных новостей для канала ХМ | Главное.\n\n'
        'Отправьте мне новость (текст, фото, видео), и я передам её на модерацию.'
    )


# Optional helper: let users ask for their own ID
async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(f"Ваш Telegram ID: {user.id}")


async def handle_news_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle news submissions from users."""
    user = update.effective_user
    message = update.message

    # Generate unique ID for this submission
    submission_id = f"{user.id}_{message.message_id}"

    # Store the submission
    pending_news[submission_id] = {
        'user_id': user.id,
        'username': user.username or user.first_name,
        'message': message
    }

    # Create approval keyboard
    keyboard = [
        [
            InlineKeyboardButton("✅ Опубликовать", callback_data=f"approve_{submission_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{submission_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send to admins
    for admin_id in ADMIN_IDS:
        if not admin_id:
            continue

        target = admin_id
        # If admin is given as @username, try to resolve to numeric id
        if admin_id.startswith('@'):
            try:
                chat = await context.bot.get_chat(admin_id)
                target = chat.id
                logger.info(f"Resolved admin {admin_id} -> {target}")
            except Exception as e:
                logger.warning(f"Could not resolve admin {admin_id}: {e}. Will try to send using original value.")

        try:
            await context.bot.send_message(
                chat_id=target,
                text=f"📰 Новое предложение от @{user.username or user.first_name} (ID: {user.id})",
                reply_markup=reply_markup
            )

            # Forward the actual content
            await message.forward(chat_id=target)
        except Exception as e:
            logger.error(f"Error sending to admin {admin_id} (target={target}): {e}")

    await update.message.reply_text(
        '✅ Ваше предложение отправлено на модерацию. Спасибо!'
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button presses for approval/rejection."""
    query = update.callback_query
    await query.answer()

    action, submission_id = query.data.split('_', 1)

    if submission_id not in pending_news:
        await query.edit_message_text('❌ Это предложение уже обработано или не найдено.')
        return

    submission = pending_news[submission_id]

    if action == 'approve':
        # Post to channel
        try:
            message = submission['message']

            # Copy message to channel (support text, photo, video)
            if getattr(message, 'text', None):
                await context.bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=message.text
                )
            elif getattr(message, 'photo', None):
                await context.bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=message.photo[-1].file_id,
                    caption=message.caption or ''
                )
            elif getattr(message, 'video', None):
                await context.bot.send_video(
                    chat_id=CHANNEL_ID,
                    video=message.video.file_id,
                    caption=message.caption or ''
                )
            else:
                # Fallback: forward the original message to the channel
                await message.forward(chat_id=CHANNEL_ID)

            # Notify user
            try:
                await context.bot.send_message(
                    chat_id=submission['user_id'],
                    text='🎉 Ваша новость опубликована в канале!'
                )
            except Exception:
                pass

            await query.edit_message_text(
                f"✅ Опубликовано в канале!\n\nОт: @{submission['username']}"
            )

        except Exception as e:
            logger.error(f"Error publishing: {e}")
            await query.edit_message_text(f'❌ Ошибка при публикации: {e}')

    elif action == 'reject':
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=submission['user_id'],
                text='❌ К сожалению, ваше предложение не было принято.'
            )
        except Exception:
            pass

        await query.edit_message_text(
            f"❌ Отклонено\n\nОт: @{submission['username']}"
        )

    # Remove from pending
    del pending_news[submission_id]


def main():
    """Start the bot."""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set!")
        return

    if not CHANNEL_ID:
        logger.error("CHANNEL_ID not set!")
        return

    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("id", id_command))  # optional helper to get your Telegram ID
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(
        filters.TEXT | filters.PHOTO | filters.VIDEO,
        handle_news_submission
    ))

    # Run the bot
    logger.info("Bot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
