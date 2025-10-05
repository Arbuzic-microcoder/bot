from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import sqlite3
from telegram.error import TelegramError, BadRequest
from datetime import datetime, timezone
import nest_asyncio
nest_asyncio.apply()


TOKEN = '8211740528:AAHYpA-tkQ3u4RAdFvYOpBANeofEnLJLLZk' 

CHANNELS = [
    '@letsteachenglish'
]

DB_FILENAME = 'subscribers.db'

# Асинхронные обработчики
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Старт", callback_data='start_button')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Нажмите кнопку "Старт", чтобы начать:', reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Подтверждаем нажатие
    if query.data == 'start_button':
        await query.edit_message_text(text="подпишись на всех t.me/letsteachenglish") # Сюда добавляем реферальные ссылки

async def send_scheduled_message(context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_FILENAME)
    c = conn.cursor()
    c.execute("SELECT user_id FROM subscribers WHERE subscribed = 1")
    users = c.fetchall()
    conn.close()

    message_text = "Это важное сообщение для всех подписчиков, которые когда-либо были подписаны на все каналы." # Награда за участие в рассылке 

    for (user_id,) in users:
        try:
            await context.bot.send_message(chat_id=user_id, text=message_text)
        except BadRequest as e:
            print(f"BadRequest: не удалось отправить сообщение пользователю {user_id}: {e}")
        except TelegramError as e:
            print(f"TelegramError: ошибка при отправке сообщения пользователю {user_id}: {e}")
        except Exception as e:
            print(f"Ошибка при отправке пользователю {user_id}: {e}")

async def get_user_status_in_channel(bot, channel_id, user_id):
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status
    except BadRequest:
        return None
    except TelegramError:
        return None

def init_db():
    conn = sqlite3.connect(DB_FILENAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS subscribers (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            subscribed BOOLEAN NOT NULL,
            joined_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def add_or_update_subscriber(user_id: int, username: str, subscribed: bool):
    conn = sqlite3.connect(DB_FILENAME)
    c = conn.cursor()
    now = datetime.utcnow().isoformat()

    c.execute('''
        INSERT INTO subscribers (user_id, username, subscribed, joined_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username,
            subscribed=excluded.subscribed,
            joined_at=excluded.joined_at
    ''', (user_id, username, subscribed, now))

    conn.commit()
    conn.close()

async def check_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id
    username = user.username or ""

    results = []
    all_subscribed = True

    for channel in CHANNELS:
        status = await get_user_status_in_channel(context.bot, channel, user_id)
        if status in ['member', 'administrator', 'creator']:
            results.append(f"Вы подписаны на канал {channel}")
        elif status is None:
            results.append(f"Не удалось проверить канал {channel}")
            all_subscribed = False
        else:
            results.append(f"Вы НЕ подписаны на канал {channel}")
            all_subscribed = False

    if all_subscribed:
        add_or_update_subscriber(user_id, username, True)
        results.append("\nВы успешно добавлены в список рассылки!")
    else:
        add_or_update_subscriber(user_id, username, False)
        results.append("\nПожалуйста, подпишитесь на все каналы, чтобы участвовать в рассылке.")

    await update.message.reply_text("\n".join(results))

async def main():
    application = ApplicationBuilder().token(TOKEN).build()

    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("check", check_subscriptions))
    application.add_handler(CallbackQueryHandler(button_handler))

    # Планируем рассылку
    target_datetime = datetime(2025, 10, 5, 18, 4, 0, tzinfo=timezone.utc) # год, месяц, день, час, минута, секунда
    now = datetime.now(timezone.utc)
    delay = (target_datetime - now).total_seconds()
    if delay > 0:
        application.job_queue.run_once(send_scheduled_message, when=delay)
        print(f"Рассылка запланирована на {target_datetime.isoformat()} (через {delay:.1f} сек)")
    else:
        print("Целевая дата уже прошла, рассылка не запланирована")

    await application.run_polling()

if __name__ == '__main__':
    init_db()
    import asyncio
    asyncio.run(main())