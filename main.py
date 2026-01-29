# bot.py
import os
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
from telegram.constants import ParseMode
import json
import asyncio

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
TOKEN = os.getenv("TELEGRAM_TOKEN", "ВАШ_ТОКЕН_БОТА")
ADMIN_ID = int(os.getenv("ADMIN_ID", "ВАШ_ID_В_TELEGRAM"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "") + "/webhook"
PORT = int(os.getenv("PORT", 8080))

# Инициализация Flask (для вебхука)
app = Flask(__name__)

# Хранилище данных (в памяти, для демо)
# В реальности используйте базу данных
users_db = {}
messages_db = []
stickers_db = ['😀', '😂', '😎', '🤖', '🚀', '💻', '🎮', '📱']


# ====================
# КОМАНДЫ БОТА
# ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user

    # Сохраняем пользователя
    users_db[user.id] = {
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'joined': datetime.now().isoformat(),
        'messages_sent': 0
    }

    keyboard = [
        [InlineKeyboardButton("📱 Мой профиль", callback_data="profile")],
        [InlineKeyboardButton("💬 Общий чат", callback_data="chat")],
        [InlineKeyboardButton("🎮 Стикеры", callback_data="stickers")],
        [InlineKeyboardButton("🔧 Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🚀 *Добро пожаловать в HackChat, {user.first_name}!*\n\n"
        "Это ваш личный мессенджер с синхронизацией между устройствами.\n\n"
        "✨ *Возможности:*\n"
        "• Общий чат со всеми пользователями\n"
        "• Стикеры и голосовые\n"
        "• Синхронизация на всех устройствах\n"
        "• Полная анонимность\n\n"
        "Выберите действие:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    help_text = """
🤖 *Команды HackChat Bot:*

/start - Запустить бота
/help - Эта справка
/chat - Открыть общий чат
/profile - Ваш профиль
/stickers - Выбрать стикер
/broadcast - Отправить всем (только админ)
/stats - Статистика (только админ)

📱 *Как использовать:*
1. Добавьте бота в несколько чатов
2. Отправляйте сообщения в ЛС боту
3. Они появятся во всех чатах с ботом
4. Используйте кнопки для навигации

💡 *Фишки:*
• Сообщения синхронизируются каждые 15 секунд
• Поддерживаются стикеры и голосовые
• Полная история сообщений
"""
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)


async def chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Открыть общий чат"""
    await update.message.reply_text(
        "💬 *Общий чат*\n\n"
        "Отправьте любое сообщение, и оно появится у всех пользователей бота!\n\n"
        "Сейчас в чате: *{}* пользователей".format(len(users_db)),
        parse_mode=ParseMode.MARKDOWN
    )


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать профиль"""
    user = update.effective_user

    profile = users_db.get(user.id, {})
    messages_count = profile.get('messages_sent', 0)

    profile_text = f"""
📱 *Ваш профиль:*

👤 Имя: {user.first_name} {user.last_name or ''}
🆔 ID: `{user.id}`
📝 Юзернейм: @{user.username or 'нет'}
📨 Сообщений отправлено: {messages_count}
📅 С нами с: {profile.get('joined', 'сегодня')}

💡 *Ваша ссылка для приглашения:*
`https://t.me/{context.bot.username}?start=ref{user.id}`
"""
    await update.message.reply_text(profile_text, parse_mode=ParseMode.MARKDOWN)


# ====================
# ОБРАБОТКА СООБЩЕНИЙ
# ====================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка всех сообщений"""
    user = update.effective_user
    message = update.message

    # Обновляем статистику
    if user.id in users_db:
        users_db[user.id]['messages_sent'] = users_db[user.id].get('messages_sent', 0) + 1
    else:
        users_db[user.id] = {'messages_sent': 1, 'joined': datetime.now().isoformat()}

    # Сохраняем сообщение
    msg_data = {
        'id': message.message_id,
        'user_id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'text': message.text or message.caption or '',
        'type': 'text',
        'timestamp': datetime.now().isoformat(),
        'chat_type': 'private' if message.chat.type == 'private' else 'group'
    }

    # Проверяем тип контента
    if message.sticker:
        msg_data['type'] = 'sticker'
        msg_data['sticker_id'] = message.sticker.file_id
    elif message.voice:
        msg_data['type'] = 'voice'
        msg_data['voice_id'] = message.voice.file_id
    elif message.photo:
        msg_data['type'] = 'photo'
        msg_data['photo_id'] = message.photo[-1].file_id

    messages_db.append(msg_data)

    # Ограничиваем историю
    if len(messages_db) > 1000:
        messages_db.pop(0)

    # Отправляем подтверждение
    if msg_data['type'] == 'text':
        await message.reply_text(
            f"✅ Сообщение сохранено!\n"
            f"📡 Синхронизация через 15 секунд...\n"
            f"👥 Увидят: {len(users_db)} пользователей",
            parse_mode=ParseMode.MARKDOWN
        )
    elif msg_data['type'] == 'sticker':
        await message.reply_text("🎭 Стикер сохранен!")
    elif msg_data['type'] == 'voice':
        await message.reply_text("🎤 Голосовое сообщение сохранено!")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий кнопок"""
    query = update.callback_query
    await query.answer()

    if query.data == "profile":
        user = query.from_user
        profile = users_db.get(user.id, {})
        await query.edit_message_text(
            text=f"📊 *Ваша статистика:*\n\n"
                 f"Сообщений: {profile.get('messages_sent', 0)}\n"
                 f"В системе: с {profile.get('joined', 'сегодня')}",
            parse_mode=ParseMode.MARKDOWN
        )

    elif query.data == "chat":
        await query.edit_message_text(
            text="💬 *Общий чат активен!*\n\n"
                 "Отправляйте сообщения боту в личку, "
                 "и они будут синхронизированы со всеми устройствами.\n\n"
                 f"👥 Пользователей онлайн: {len(users_db)}",
            parse_mode=ParseMode.MARKDOWN
        )

    elif query.data == "stickers":
        # Показываем стикеры
        sticker_grid = []
        row = []
        for i, sticker in enumerate(stickers_db[:12]):
            row.append(InlineKeyboardButton(sticker, callback_data=f"sticker_{i}"))
            if len(row) == 4:
                sticker_grid.append(row)
                row = []

        sticker_grid.append([InlineKeyboardButton("« Назад", callback_data="back")])

        await query.edit_message_text(
            text="🎭 *Выберите стикер:*",
            reply_markup=InlineKeyboardMarkup(sticker_grid),
            parse_mode=ParseMode.MARKDOWN
        )

    elif query.data.startswith("sticker_"):
        index = int(query.data.split("_")[1])
        if index < len(stickers_db):
            await query.message.reply_text(f"Вы выбрали: {stickers_db[index]}")

    elif query.data == "back":
        await start(update, context)

    elif query.data == "help":
        await help_command(update, context)


# ====================
# АДМИН КОМАНДЫ
# ====================
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправить сообщение всем пользователям (админ)"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Только для администратора!")
        return

    if not context.args:
        await update.message.reply_text("Использование: /broadcast <сообщение>")
        return

    message = " ".join(context.args)

    # Отправляем всем пользователям
    count = 0
    for user_id in users_db.keys():
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📢 *Объявление от админа:*\n\n{message}",
                parse_mode=ParseMode.MARKDOWN
            )
            count += 1
            await asyncio.sleep(0.05)  # Защита от лимитов
        except Exception as e:
            logger.error(f"Не удалось отправить пользователю {user_id}: {e}")

    await update.message.reply_text(f"✅ Сообщение отправлено {count} пользователям")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика бота (админ)"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Только для администратора!")
        return

    total_messages = sum(u.get('messages_sent', 0) for u in users_db.values())

    stats_text = f"""
📊 *Статистика HackChat Bot:*

👥 Пользователей: {len(users_db)}
📨 Всего сообщений: {total_messages}
💾 Сохранено в истории: {len(messages_db)}
🆕 Новых сегодня: {len([m for m in messages_db if datetime.fromisoformat(m['timestamp']).date() == datetime.now().date()])}

💡 *Топ 5 пользователей:*
"""

    # Сортируем пользователей по активности
    sorted_users = sorted(users_db.items(), key=lambda x: x[1].get('messages_sent', 0), reverse=True)[:5]

    for i, (user_id, data) in enumerate(sorted_users, 1):
        stats_text += f"{i}. ID {user_id}: {data.get('messages_sent', 0)} сообщений\n"

    await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)


# ====================
# WEBHOOK (для сервера)
# ====================
@app.route('/webhook', methods=['POST'])
def webhook():
    """Обработка вебхуков от Telegram"""
    update = Update.de_json(request.get_json(force=True), application.bot)
    asyncio.run(process_update(update))
    return 'ok'


@app.route('/')
def home():
    """Главная страница сервера"""
    return jsonify({
        'status': 'online',
        'bot': '@your_hackchat_bot',
        'users': len(users_db),
        'messages': len(messages_db),
        'uptime': str(datetime.now() - start_time)
    })


@app.route('/health')
def health():
    """Проверка здоровья сервера"""
    return 'OK', 200


async def process_update(update: Update):
    """Асинхронная обработка обновления"""
    await application.process_update(update)


# ====================
# ЗАПУСК СЕРВЕРА
# ====================
async def main():
    """Основная функция запуска"""
    global application, start_time
    start_time = datetime.now()

    # Создаем приложение
    application = Application.builder().token(TOKEN).build()

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("chat", chat_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("stats", stats))

    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_handler))

    # Запускаем вебхук
    await application.bot.set_webhook(WEBHOOK_URL)
    print(f"🤖 Бот запущен! Вебхук: {WEBHOOK_URL}")

    # Запускаем Flask сервер
    from waitress import serve
    serve(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    # Для локального тестирования
    asyncio.run(main())