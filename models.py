# models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.BigInteger, unique=True, nullable=False)
    username = db.Column(db.String(100))
    balance_stars = db.Column(db.Integer, default=0)
    balance_rub = db.Column(db.Float, default=0)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    nfts = db.relationship('NFT', backref='owner', lazy=True)
    purchases = db.relationship('Transaction', foreign_keys='Transaction.buyer_id', backref='buyer', lazy=True)
    sales = db.relationship('Transaction', foreign_keys='Transaction.seller_id', backref='seller', lazy=True)

class NFT(db.Model):
    __tablename__ = 'nfts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    file_id = db.Column(db.String(200), nullable=False)  # Telegram file_id
    file_name = db.Column(db.String(200))
    file_path = db.Column(db.String(500))
    file_size = db.Column(db.Integer)
    file_type = db.Column(db.String(50))
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    price = db.Column(db.Integer)  # Цена в Stars
    status = db.Column(db.String(50), default='pending')  # pending, for_sale, sold, transferred
    views = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sold_at = db.Column(db.DateTime)
    
    transaction = db.relationship('Transaction', backref='nft', uselist=False)

class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    nft_id = db.Column(db.Integer, db.ForeignKey('nfts.id'), nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount_stars = db.Column(db.Integer, nullable=False)
    amount_rub = db.Column(db.Float)
    status = db.Column(db.String(50), default='completed')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class TransferRequest(db.Model):
    __tablename__ = 'transfer_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    nft_id = db.Column(db.Integer, db.ForeignKey('nfts.id'), nullable=False)
    from_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    to_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    transfer_code = db.Column(db.String(100), unique=True)
    status = db.Column(db.String(50), default='pending')  # pending, completed, expired
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)