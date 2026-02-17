# app.py
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, current_user, logout_user
import requests
from datetime import datetime
import uuid
import hashlib
import hmac

from config import BOT_MAIN_TOKEN, BOT_RECEIVER_TOKEN, WEBHOOK_URL
from models import db, User, NFT, Transaction, TransferRequest

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nft_market.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Telegram Auth
def check_telegram_auth(telegram_data):
    """Проверка подлинности данных от Telegram"""
    bot_token = BOT_MAIN_TOKEN
    check_hash = telegram_data.pop('hash')
    data_check_arr = [f"{key}={value}" for key, value in sorted(telegram_data.items())]
    data_check_string = "\n".join(data_check_arr)
    
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    
    return hash == check_hash

@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')

@app.route('/login')
def login():
    """Страница входа через Telegram"""
    return render_template('login.html')

@app.route('/auth', methods=['POST'])
def auth():
    """Обработка авторизации через Telegram"""
    data = request.form.to_dict()
    
    if check_telegram_auth(data):
        telegram_id = int(data['id'])
        username = data.get('username', '')
        
        # Ищем или создаем пользователя
        user = User.query.filter_by(telegram_id=telegram_id).first()
        if not user:
            user = User(telegram_id=telegram_id, username=username)
            db.session.add(user)
            db.session.commit()
        
        login_user(user)
        
        return jsonify({
            'success': True,
            'redirect': url_for('profile')
        })
    
    return jsonify({
        'success': False,
        'error': 'Invalid authentication'
    }), 400

@app.route('/market')
@login_required
def market():
    """Страница маркета"""
    page = request.args.get('page', 1, type=int)
    per_page = 12
    
    nfts = NFT.query.filter_by(status='for_sale').order_by(NFT.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('market.html', nfts=nfts)

@app.route('/nft/<int:nft_id>')
@login_required
def view_nft(nft_id):
    """Просмотр NFT"""
    nft = NFT.query.get_or_404(nft_id)
    
    # Увеличиваем просмотры
    nft.views += 1
    db.session.commit()
    
    seller = User.query.get(nft.user_id)
    
    return render_template('nft_detail.html', nft=nft, seller=seller)

@app.route('/inventory')
@login_required
def inventory():
    """Инвентарь пользователя"""
    nfts = NFT.query.filter_by(user_id=current_user.id, status='owned').all()
    return render_template('inventory.html', nfts=nfts)

@app.route('/profile')
@login_required
def profile():
    """Профиль пользователя"""
    return render_template('profile.html', user=current_user)

@app.route('/api/buy/<int:nft_id>', methods=['POST'])
@login_required
def buy_nft(nft_id):
    """API для покупки NFT"""
    nft = NFT.query.get_or_404(nft_id)
    
    if nft.status != 'for_sale':
        return jsonify({
            'success': False,
            'error': 'NFT not for sale'
        }), 400
    
    if nft.user_id == current_user.id:
        return jsonify({
            'success': False,
            'error': 'Cannot buy your own NFT'
        }), 400
    
    if current_user.balance_stars < nft.price:
        return jsonify({
            'success': False,
            'error': 'Insufficient balance'
        }), 400
    
    # Создаем транзакцию
    transaction = Transaction(
        nft_id=nft.id,
        buyer_id=current_user.id,
        seller_id=nft.user_id,
        amount_stars=nft.price,
        amount_rub=nft.price * 10  # Конвертация в рубли
    )
    
    # Обновляем балансы
    current_user.balance_stars -= nft.price
    seller = User.query.get(nft.user_id)
    seller.balance_stars += nft.price
    
    # Обновляем статус NFT
    nft.status = 'sold'
    nft.user_id = current_user.id
    nft.sold_at = datetime.utcnow()
    
    db.session.add(transaction)
    db.session.commit()
    
    # Уведомляем бота о продаже
    notify_bot_about_sale(transaction)
    
    return jsonify({
        'success': True,
        'message': 'Purchase successful',
        'nft_id': nft.id
    })

@app.route('/api/transfer', methods=['POST'])
@login_required
def transfer_nft():
    """API для передачи NFT"""
    data = request.json
    nft_id = data.get('nft_id')
    to_username = data.get('to_username')
    
    nft = NFT.query.get_or_404(nft_id)
    
    if nft.user_id != current_user.id:
        return jsonify({
            'success': False,
            'error': 'Not your NFT'
        }), 403
    
    # Ищем получателя
    recipient = User.query.filter_by(username=to_username).first()
    if not recipient:
        return jsonify({
            'success': False,
            'error': 'User not found'
        }), 404
    
    # Создаем код передачи
    transfer_code = str(uuid.uuid4())[:8].upper()
    
    transfer = TransferRequest(
        nft_id=nft.id,
        from_user_id=current_user.id,
        to_user_id=recipient.id,
        transfer_code=transfer_code,
        expires_at=datetime.utcnow().replace(hour=24, minute=0, second=0)
    )
    
    db.session.add(transfer)
    db.session.commit()
    
    # Уведомляем бота
    notify_bot_about_transfer(transfer)
    
    return jsonify({
        'success': True,
        'transfer_code': transfer_code,
        'message': f'Transfer code created. Share it with @{to_username}'
    })

@app.route('/api/deposit', methods=['POST'])
@login_required
def deposit():
    """API для пополнения через Stars"""
    data = request.json
    amount = data.get('amount', 0)
    
    if amount < 1:
        return jsonify({
            'success': False,
            'error': 'Invalid amount'
        }), 400
    
    # Создаем ссылку на оплату Stars
    payment_link = create_stars_payment_link(current_user.id, amount)
    
    return jsonify({
        'success': True,
        'payment_link': payment_link
    })

@app.route('/api/stats')
@login_required
def get_stats():
    """API для получения статистики"""
    user_id = current_user.id
    
    total_nfts = NFT.query.filter_by(user_id=user_id).count()
    sold_nfts = NFT.query.filter_by(user_id=user_id, status='sold').count()
    total_earned = db.session.query(db.func.sum(Transaction.amount_stars)).filter_by(seller_id=user_id).scalar() or 0
    total_spent = db.session.query(db.func.sum(Transaction.amount_stars)).filter_by(buyer_id=user_id).scalar() or 0
    
    return jsonify({
        'success': True,
        'stats': {
            'total_nfts': total_nfts,
            'sold_nfts': sold_nfts,
            'total_earned': total_earned,
            'total_spent': total_spent,
            'balance': current_user.balance_stars
        }
    })

def notify_bot_about_sale(transaction):
    """Уведомление бота о продаже"""
    try:
        # Отправляем запрос к боту
        requests.post(f"{WEBHOOK_URL}/api/sale_notification", json={
            'transaction_id': transaction.id,
            'nft_id': transaction.nft_id,
            'buyer_id': transaction.buyer_id,
            'seller_id': transaction.seller_id,
            'amount': transaction.amount_stars
        })
    except:
        pass

def notify_bot_about_transfer(transfer):
    """Уведомление бота о передаче"""
    try:
        requests.post(f"{WEBHOOK_URL}/api/transfer_notification", json={
            'transfer_id': transfer.id,
            'nft_id': transfer.nft_id,
            'from_user': transfer.from_user_id,
            'to_user': transfer.to_user_id,
            'code': transfer.transfer_code
        })
    except:
        pass

def create_stars_payment_link(user_id: int, amount: int) -> str:
    """Создание ссылки на оплату Stars"""
    # Используем Telegram Payment API
    return f"https://t.me/{BOT_MAIN_TOKEN.split(':')[0]}/?start=pay_{user_id}_{amount}"

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5002)