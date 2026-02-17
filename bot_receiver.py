# bot_receiver.py
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from flask import Flask, request, jsonify
import uuid
from datetime import datetime, timedelta
import os
import aiohttp

from config import BOT_RECEIVER_TOKEN, WEBHOOK_URL, UPLOAD_FOLDER
from database import Database

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_RECEIVER_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

db = Database()

# Хранилище временных данных пользователей
user_sessions = {}

@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    """Стартовое сообщение"""
    text = """
🤖 <b>NFT Receiver Bot</b>

Я принимаю NFT для маркета! 

<b>Что я умею:</b>
✅ Принимать NFT файлы
✅ Генерировать коды передачи
✅ Отправлять NFT получателям

<b>Как отправить NFT:</b>
1️⃣ Просто отправьте мне файл NFT
2️⃣ Укажите цену и описание
3️⃣ Получите код для выставления в маркете

<b>Как получить NFT:</b>
1️⃣ Получите код передачи от отправителя
2️⃣ Отправьте мне команду /get <код>
3️⃣ Я пришлю вам NFT
    """
    
    await message.answer(text)

@dp.message_handler(commands=['get'])
async def get_nft_command(message: types.Message):
    """Получение NFT по коду"""
    args = message.get_args()
    
    if not args:
        await message.answer("❌ Укажите код: /get ABC123")
        return
    
    transfer_code = args.strip().upper()
    
    # Ищем код в базе
    transfer = db.get_transfer_by_code(transfer_code)
    
    if not transfer:
        await message.answer("❌ Код не найден")
        return
    
    if transfer['status'] != 'pending':
        await message.answer("❌ Код уже использован или истек")
        return
    
    if datetime.now() > transfer['expires_at']:
        await message.answer("❌ Срок действия кода истек")
        db.update_transfer_status(transfer_code, 'expired')
        return
    
    # Получаем NFT
    nft = db.get_nft_by_id(transfer['nft_id'])
    
    if not nft:
        await message.answer("❌ NFT не найден")
        return
    
    # Отправляем файл
    try:
        if nft['file_type'] in ['photo', 'image']:
            await bot.send_photo(
                message.chat.id,
                nft['file_id'],
                caption=f"🎨 <b>NFT получен!</b>\n\n{nft['title'] or ''}\n{nft['description'] or ''}"
            )
        elif nft['file_type'] == 'video':
            await bot.send_video(
                message.chat.id,
                nft['file_id'],
                caption=f"🎨 <b>NFT получен!</b>\n\n{nft['title'] or ''}\n{nft['description'] or ''}"
            )
        else:
            await bot.send_document(
                message.chat.id,
                nft['file_id'],
                caption=f"🎨 <b>NFT получен!</b>\n\n{nft['title'] or ''}\n{nft['description'] or ''}"
            )
        
        # Обновляем статус передачи
        db.complete_transfer(transfer['nft_id'], message.from_user.id, transfer_code)
        
        # Уведомляем отправителя
        await bot.send_message(
            transfer['from_user_id'],
            f"✅ Ваш NFT был получен пользователем @{message.from_user.username}"
        )
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при отправке: {str(e)}")
        logging.error(f"Error sending NFT: {e}")

@dp.message_handler(content_types=['document', 'photo', 'video', 'animation'])
async def handle_nft_upload(message: types.Message):
    """Обработка загруженных NFT"""
    user_id = message.from_user.id
    
    # Сохраняем информацию о файле
    file_info = await extract_file_info(message)
    
    if not file_info:
        await message.answer("❌ Не удалось обработать файл")
        return
    
    # Сохраняем сессию
    session_id = str(uuid.uuid4())[:8]
    user_sessions[session_id] = {
        'user_id': user_id,
        'file_info': file_info,
        'step': 'waiting_title'
    }
    
    # Запрашиваем название
    text = f"""
📁 <b>Файл получен!</b>

<b>Имя:</b> {file_info['file_name']}
<b>Тип:</b> {file_info['file_type']}
<b>Размер:</b> {file_info['file_size']} байт

Теперь укажите <b>название</b> NFT:
(или отправьте /skip чтобы пропустить)
    """
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_{session_id}"))
    
    await message.answer(text, reply_markup=keyboard)
    
    # Сохраняем ID сообщения для редактирования
    user_sessions[session_id]['message_id'] = message.message_id + 1

@dp.message_handler(lambda message: is_waiting_for_input(message.from_user.id))
async def handle_text_input(message: types.Message):
    """Обработка текстового ввода"""
    user_id = message.from_user.id
    
    # Находим сессию пользователя
    session_id = find_user_session(user_id)
    
    if not session_id:
        return
    
    session = user_sessions[session_id]
    
    if session['step'] == 'waiting_title':
        # Сохраняем название
        session['title'] = message.text
        session['step'] = 'waiting_description'
        
        await message.answer(
            "📝 Теперь укажите <b>описание</b> NFT:\n"
            "(или отправьте /skip чтобы пропустить)"
        )
        
    elif session['step'] == 'waiting_description':
        # Сохраняем описание
        session['description'] = message.text
        session['step'] = 'waiting_price'
        
        await message.answer(
            "💰 Укажите <b>цену</b> в Stars:\n"
            "Пример: 100"
        )
        
    elif session['step'] == 'waiting_price':
        try:
            price = int(message.text)
            if price < 1:
                raise ValueError()
            
            session['price'] = price
            
            # Создаем NFT в базе
            nft_data = {
                'user_id': user_id,
                'file_id': session['file_info']['file_id'],
                'file_name': session['file_info']['file_name'],
                'file_path': session['file_info']['file_path'],
                'file_size': session['file_info']['file_size'],
                'file_type': session['file_info']['file_type'],
                'title': session.get('title', ''),
                'description': session.get('description', ''),
                'price': price,
                'status': 'pending'
            }
            
            nft_id = db.add_nft(nft_data)
            
            # Генерируем код передачи
            transfer_code = generate_transfer_code()
            expires_at = datetime.now() + timedelta(hours=24)
            
            # Создаем запрос на передачу
            db.create_transfer_request(nft_id, user_id, transfer_code, expires_at)
            
            # Отправляем код пользователю
            text = f"""
✅ <b>NFT готов к продаже!</b>

<b>Код передачи:</b> <code>{transfer_code}</code>

<b>Как выставить на продажу:</b>
1️⃣ Перейдите в основной бот: @NFTMarketBot
2️⃣ Отправьте команду /sell {transfer_code}
3️⃣ Заполните информацию

<b>Код действителен 24 часа</b>
            """
            
            keyboard = InlineKeyboardMarkup()
            keyboard.add(
                InlineKeyboardButton("📋 Копировать код", callback_data=f"copy_{transfer_code}"),
                InlineKeyboardButton("✅ Готово", callback_data="done")
            )
            
            await message.answer(text, reply_markup=keyboard)
            
            # Очищаем сессию
            del user_sessions[session_id]
            
        except ValueError:
            await message.answer("❌ Укажите корректное число (например: 100)")

@dp.callback_query_handler(lambda c: c.data.startswith('cancel_'))
async def cancel_session(callback_query: types.CallbackQuery):
    """Отмена сессии"""
    session_id = callback_query.data.split('_')[1]
    
    if session_id in user_sessions:
        del user_sessions[session_id]
    
    await callback_query.message.edit_text(
        "❌ Операция отменена",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("◀️ Назад", callback_data="back_to_start")
        )
    )

async def extract_file_info(message: types.Message):
    """Извлечение информации о файле"""
    try:
        if message.document:
            file = message.document
            file_id = file.file_id
            file_name = file.file_name
            file_type = 'document'
            file_size = file.file_size
        elif message.photo:
            file = message.photo[-1]
            file_id = file.file_id
            file_name = f"photo_{datetime.now().timestamp()}.jpg"
            file_type = 'photo'
            file_size = file.file_size
        elif message.video:
            file = message.video
            file_id = file.file_id
            file_name = file.file_name or f"video_{datetime.now().timestamp()}.mp4"
            file_type = 'video'
            file_size = file.file_size
        elif message.animation:
            file = message.animation
            file_id = file.file_id
            file_name = file.file_name or f"animation_{datetime.now().timestamp()}.gif"
            file_type = 'animation'
            file_size = file.file_size
        else:
            return None
        
        # Скачиваем файл
        file_path = await download_file(file_id, file_name)
        
        return {
            'file_id': file_id,
            'file_name': file_name,
            'file_type': file_type,
            'file_size': file_size,
            'file_path': file_path
        }
    except Exception as e:
        logging.error(f"Error extracting file info: {e}")
        return None

async def download_file(file_id: str, file_name: str) -> str:
    """Скачивание файла с Telegram"""
    file = await bot.get_file(file_id)
    file_path = file.file_path
    
    # Создаем папку если её нет
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    # Генерируем уникальное имя
    unique_name = f"{uuid.uuid4()}_{file_name}"
    local_path = os.path.join(UPLOAD_FOLDER, unique_name)
    
    # Скачиваем файл
    await bot.download_file(file_path, local_path)
    
    return local_path

def generate_transfer_code() -> str:
    """Генерация уникального кода передачи"""
    import random
    import string
    
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        if not db.check_transfer_code_exists(code):
            return code

def is_waiting_for_input(user_id: int) -> bool:
    """Проверка, ожидает ли пользователь ввод"""
    for session in user_sessions.values():
        if session['user_id'] == user_id:
            return True
    return False

def find_user_session(user_id: int) -> str:
    """Поиск сессии пользователя"""
    for session_id, session in user_sessions.items():
        if session['user_id'] == user_id:
            return session_id
    return None

# Webhook для связи с основным ботом
@app.route('/webhook_receiver', methods=['POST'])
def webhook_receiver():
    """Получение обновлений от Telegram"""
    update = types.Update.de_json(request.get_json(), bot)
    dp.process_update(update)
    return 'ok', 200

@app.route('/api/transfer_status/<code>', methods=['GET'])
def get_transfer_status(code):
    """API для проверки статуса передачи"""
    transfer = db.get_transfer_by_code(code)
    
    if transfer:
        return jsonify({
            'success': True,
            'status': transfer['status'],
            'nft_id': transfer['nft_id'],
            'expires_at': transfer['expires_at'].isoformat()
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Transfer code not found'
        }), 404

if __name__ == '__main__':
    from flask import Flask
    app = Flask(__name__)
    
    # Устанавливаем webhook
    bot.set_webhook(f"{WEBHOOK_URL}{WEBHOOK_RECEIVER_PATH}")
    
    # Запускаем Flask приложение
    app.run(host='0.0.0.0', port=5001)