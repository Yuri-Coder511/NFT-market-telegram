# bot_main.py
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from flask import Flask, request, jsonify
import requests
from datetime import datetime
import json

from config import BOT_MAIN_TOKEN, WEBHOOK_URL, ADMIN_IDS
from database import Database

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_MAIN_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

db = Database()

# Клавиатуры
def get_main_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🛍 Маркет", callback_data="market"),
        InlineKeyboardButton("🎒 Инвентарь", callback_data="inventory"),
        InlineKeyboardButton("💰 Продать", callback_data="sell_menu"),
        InlineKeyboardButton("⭐️ Пополнить", callback_data="deposit"),
        InlineKeyboardButton("📊 Статистика", callback_data="stats"),
        InlineKeyboardButton("⚙️ Профиль", callback_data="profile"),
        InlineKeyboardButton("🔄 Передать NFT", callback_data="transfer_menu")
    )
    return keyboard

@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Регистрация пользователя
    db.add_user(user_id, username)
    
    welcome_text = f"""
🎨 <b>Добро пожаловать в NFT Маркет!</b>

<b>Ваш ID:</b> <code>{user_id}</code>

<b>Как продать NFT:</b>
1️⃣ Отправьте NFT боту-приемнику: @NFTReceiverBot
2️⃣ Бот выдаст вам код подтверждения
3️⃣ Введите код здесь для выставления на продажу

<b>Как купить:</b>
💰 Пополните баланс через Stars
🛍 Выберите NFT в маркете
✅ Подтвердите покупку
    """
    
    await message.answer(welcome_text, reply_markup=get_main_keyboard())

@dp.message_handler()
async def handle_message(message: types.Message):
    """Обработка текстовых сообщений"""
    user_id = message.from_user.id
    
    # Проверяем, ожидает ли пользователь ввод кода передачи
    state = db.get_user_state(user_id)
    
    if state and state['action'] == 'waiting_transfer_code':
        transfer_code = message.text.strip()
        
        # Проверяем код в базе
        transfer = db.get_transfer_by_code(transfer_code)
        
        if transfer and transfer['status'] == 'pending':
            # Привязываем NFT к пользователю
            nft_id = transfer['nft_id']
            success = db.complete_transfer(nft_id, user_id)
            
            if success:
                await message.answer(
                    f"✅ NFT успешно получен!\n"
                    f"Теперь он в вашем инвентаре",
                    reply_markup=get_main_keyboard()
                )
                
                # Уведомляем отправителя
                await bot.send_message(
                    transfer['from_user_id'],
                    f"✅ Пользователь @{message.from_user.username} получил ваш NFT!"
                )
            else:
                await message.answer("❌ Ошибка при получении NFT")
        else:
            await message.answer("❌ Недействительный код передачи")
        
        db.clear_user_state(user_id)
        return
    
    # Обработка других команд
    await message.answer("Используйте кнопки меню")

@dp.callback_query_handler(lambda c: c.data == 'market')
async def show_market(callback_query: types.CallbackQuery):
    """Показывает маркет NFT"""
    page = 1
    await show_market_page(callback_query, page)

async def show_market_page(callback_query: types.CallbackQuery, page: int):
    """Показывает страницу маркета"""
    nfts = db.get_active_sales(page=page, per_page=6)
    total_pages = db.get_total_pages()
    
    if not nfts:
        await callback_query.message.edit_text(
            "📭 Маркет пуст\n"
            "Станьте первым продавцом!",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")
            )
        )
        return
    
    text = f"🛍 <b>Маркет NFT</b> (Страница {page}/{total_pages})\n\n"
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    for nft in nfts:
        user = db.get_user_by_id(nft['user_id'])
        text += f"🖼 <b>{nft['title'] or nft['file_name']}</b>\n"
        text += f"💰 Цена: {nft['price']} ⭐️\n"
        text += f"👤 Продавец: @{user['username'] or 'Аноним'}\n"
        text += f"👀 Просмотров: {nft['views']}\n"
        text += f"🆔 ID: {nft['id']}\n"
        text += "➖➖➖➖➖➖➖\n"
        
        keyboard.add(
            InlineKeyboardButton(f"👀 Смотреть #{nft['id']}", callback_data=f"view_{nft['id']}"),
            InlineKeyboardButton(f"💰 Купить", callback_data=f"buy_{nft['id']}")
        )
    
    # Пагинация
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"market_page_{page-1}"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"market_page_{page+1}"))
    
    if nav_buttons:
        keyboard.row(*nav_buttons)
    
    keyboard.add(InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main"))
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith('view_'))
async def view_nft(callback_query: types.CallbackQuery):
    """Просмотр NFT"""
    nft_id = int(callback_query.data.split('_')[1])
    user_id = callback_query.from_user.id
    
    # Увеличиваем счетчик просмотров
    db.increment_views(nft_id)
    
    nft = db.get_nft_by_id(nft_id)
    seller = db.get_user_by_id(nft['user_id'])
    
    text = f"""
🖼 <b>{nft['title'] or nft['file_name']}</b>

📝 <b>Описание:</b>
{nft['description'] or 'Нет описания'}

💰 <b>Цена:</b> {nft['price']} ⭐️
👤 <b>Продавец:</b> @{seller['username'] or 'Аноним'}
📅 <b>Дата:</b> {nft['created_at']}
👀 <b>Просмотров:</b> {nft['views'] + 1}
    """
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("💰 Купить", callback_data=f"buy_{nft_id}"),
        InlineKeyboardButton("◀️ Назад", callback_data="market")
    )
    
    # Отправляем медиа
    if nft['file_type'] in ['photo', 'image']:
        await bot.send_photo(
            callback_query.message.chat.id,
            nft['file_id'],
            caption=text,
            reply_markup=keyboard
        )
    elif nft['file_type'] == 'video':
        await bot.send_video(
            callback_query.message.chat.id,
            nft['file_id'],
            caption=text,
            reply_markup=keyboard
        )
    else:
        await bot.send_document(
            callback_query.message.chat.id,
            nft['file_id'],
            caption=text,
            reply_markup=keyboard
        )
    
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == 'transfer_menu')
async def transfer_menu(callback_query: types.CallbackQuery):
    """Меню передачи NFT"""
    text = """
🔄 <b>Передача NFT</b>

Вы можете передать NFT другому пользователю двумя способами:

<b>1️⃣ Через бота-приемник</b>
• Отправьте NFT боту @NFTReceiverBot
• Укажите ID получателя
• Получите код передачи
• Получатель вводит код в боте

<b>2️⃣ Через сайт</b>
• Зайдите в инвентарь на сайте
• Нажмите "Передать"
• Введите ID получателя
    """
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("📤 Отправить NFT", callback_data="initiate_transfer"),
        InlineKeyboardButton("📥 Получить NFT", callback_data="receive_nft"),
        InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")
    )
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == 'initiate_transfer')
async def initiate_transfer(callback_query: types.CallbackQuery):
    """Инициирование передачи NFT"""
    user_id = callback_query.from_user.id
    nfts = db.get_user_nfts(user_id, status='owned')
    
    if not nfts:
        await callback_query.answer("У вас нет NFT для передачи", show_alert=True)
        return
    
    text = "Выберите NFT для передачи:\n\n"
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    for nft in nfts[:10]:
        keyboard.add(
            InlineKeyboardButton(
                f"{nft['title'] or nft['file_name']}",
                callback_data=f"transfer_nft_{nft['id']}"
            )
        )
    
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data="transfer_menu"))
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)

# Webhook для связи с сайтом
@app.route('/webhook', methods=['POST'])
def webhook():
    """Получение обновлений от Telegram"""
    update = types.Update.de_json(request.get_json(), bot)
    dp.process_update(update)
    return 'ok', 200

@app.route('/api/transfer_nft', methods=['POST'])
def api_transfer_nft():
    """API для передачи NFT через сайт"""
    data = request.json
    nft_id = data.get('nft_id')
    to_user_id = data.get('to_user_id')
    
    # Создаем запрос на передачу
    transfer_code = db.create_transfer_request(nft_id, to_user_id)
    
    return jsonify({
        'success': True,
        'transfer_code': transfer_code,
        'message': 'Код передачи создан'
    })

if __name__ == '__main__':
    from flask import Flask
    app = Flask(__name__)
    
    # Устанавливаем webhook
    bot.set_webhook(f"{WEBHOOK_URL}{WEBHOOK_PATH}")
    
    # Запускаем Flask приложение
    app.run(host='0.0.0.0', port=5000)