# database.py
import sqlite3
from datetime import datetime
import json

class Database:
    def __init__(self, db_path='nft_market.db'):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def init_db(self):
        """Инициализация базы данных"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE,
                    username TEXT,
                    balance_stars INTEGER DEFAULT 0,
                    balance_rub REAL DEFAULT 0,
                    is_admin BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица NFT
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS nfts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    file_id TEXT,
                    file_name TEXT,
                    file_path TEXT,
                    file_size INTEGER,
                    file_type TEXT,
                    title TEXT,
                    description TEXT,
                    price INTEGER,
                    status TEXT DEFAULT 'pending',
                    views INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    sold_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            # Таблица транзакций
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nft_id INTEGER,
                    buyer_id INTEGER,
                    seller_id INTEGER,
                    amount_stars INTEGER,
                    amount_rub REAL,
                    status TEXT DEFAULT 'completed',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (nft_id) REFERENCES nfts (id),
                    FOREIGN KEY (buyer_id) REFERENCES users (id),
                    FOREIGN KEY (seller_id) REFERENCES users (id)
                )
            ''')
            
            # Таблица запросов на передачу
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transfer_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nft_id INTEGER,
                    from_user_id INTEGER,
                    to_user_id INTEGER,
                    transfer_code TEXT UNIQUE,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    FOREIGN KEY (nft_id) REFERENCES nfts (id),
                    FOREIGN KEY (from_user_id) REFERENCES users (id),
                    FOREIGN KEY (to_user_id) REFERENCES users (id)
                )
            ''')
            
            # Таблица состояний пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_states (
                    user_id INTEGER PRIMARY KEY,
                    action TEXT,
                    data TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
    
    def add_user(self, telegram_id, username):
        """Добавление нового пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO users (telegram_id, username)
                VALUES (?, ?)
            ''', (telegram_id, username))
            conn.commit()
    
    def get_user_by_id(self, user_id):
        """Получение пользователя по ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'telegram_id': row[1],
                    'username': row[2],
                    'balance_stars': row[3],
                    'balance_rub': row[4],
                    'is_admin': row[5],
                    'created_at': row[6]
                }
            return None
    
    def get_user_by_telegram_id(self, telegram_id):
        """Получение пользователя по Telegram ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'telegram_id': row[1],
                    'username': row[2],
                    'balance_stars': row[3],
                    'balance_rub': row[4],
                    'is_admin': row[5],
                    'created_at': row[6]
                }
            return None
    
    def get_user_balance(self, user_id):
        """Получение баланса пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT balance_stars FROM users WHERE id = ?', (user_id,))
            row = cursor.fetchone()
            return row[0] if row else 0
    
    def add_nft(self, nft_data):
        """Добавление NFT"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO nfts 
                (user_id, file_id, file_name, file_path, file_size, file_type, title, description, price, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                nft_data['user_id'],
                nft_data['file_id'],
                nft_data['file_name'],
                nft_data.get('file_path'),
                nft_data.get('file_size'),
                nft_data.get('file_type'),
                nft_data.get('title'),
                nft_data.get('description'),
                nft_data.get('price'),
                nft_data.get('status', 'pending')
            ))
            conn.commit()
            return cursor.lastrowid
    
    def get_nft_by_id(self, nft_id):
        """Получение NFT по ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT n.*, u.username as seller_username 
                FROM nfts n
                LEFT JOIN users u ON n.user_id = u.id
                WHERE n.id = ?
            ''', (nft_id,))
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'user_id': row[1],
                    'file_id': row[2],
                    'file_name': row[3],
                    'file_path': row[4],
                    'file_size': row[5],
                    'file_type': row[6],
                    'title': row[7],
                    'description': row[8],
                    'price': row[9],
                    'status': row[10],
                    'views': row[11],
                    'created_at': row[12],
                    'sold_at': row[13],
                    'seller_username': row[14]
                }
            return None
    
    def get_active_sales(self, page=1, per_page=12):
        """Получение активных продаж"""
        offset = (page - 1) * per_page
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT n.*, u.username as seller_username 
                FROM nfts n
                LEFT JOIN users u ON n.user_id = u.id
                WHERE n.status = 'for_sale'
                ORDER BY n.created_at DESC
                LIMIT ? OFFSET ?
            ''', (per_page, offset))
            rows = cursor.fetchall()
            
            nfts = []
            for row in rows:
                nfts.append({
                    'id': row[0],
                    'user_id': row[1],
                    'file_id': row[2],
                    'file_name': row[3],
                    'file_path': row[4],
                    'file_size': row[5],
                    'file_type': row[6],
                    'title': row[7],
                    'description': row[8],
                    'price': row[9],
                    'status': row[10],
                    'views': row[11],
                    'created_at': row[12],
                    'sold_at': row[13],
                    'seller_username': row[14]
                })
            return nfts
    
    def get_user_nfts(self, user_id, status=None):
        """Получение NFT пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute('''
                    SELECT * FROM nfts 
                    WHERE user_id = ? AND status = ?
                    ORDER BY created_at DESC
                ''', (user_id, status))
            else:
                cursor.execute('''
                    SELECT * FROM nfts 
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                ''', (user_id,))
            
            rows = cursor.fetchall()
            nfts = []
            for row in rows:
                nfts.append({
                    'id': row[0],
                    'user_id': row[1],
                    'file_id': row[2],
                    'file_name': row[3],
                    'file_path': row[4],
                    'file_size': row[5],
                    'file_type': row[6],
                    'title': row[7],
                    'description': row[8],
                    'price': row[9],
                    'status': row[10],
                    'views': row[11],
                    'created_at': row[12],
                    'sold_at': row[13]
                })
            return nfts
    
    def increment_views(self, nft_id):
        """Увеличение счетчика просмотров"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE nfts 
                SET views = views + 1 
                WHERE id = ?
            ''', (nft_id,))
            conn.commit()
    
    def can_sell_nft(self, user_id):
        """Проверка права на продажу"""
        # Здесь можно добавить логику проверки
        return True
    
    def set_user_state(self, user_id, action, data=None):
        """Установка состояния пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO user_states (user_id, action, data, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', (user_id, action, json.dumps(data) if data else None))
            conn.commit()
    
    def get_user_state(self, user_id):
        """Получение состояния пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT action, data FROM user_states WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            if row:
                return {
                    'action': row[0],
                    'data': json.loads(row[1]) if row[1] else None
                }
            return None
    
    def clear_user_state(self, user_id):
        """Очистка состояния пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM user_states WHERE user_id = ?', (user_id,))
            conn.commit()
    
    def create_transfer_request(self, nft_id, from_user_id, transfer_code, expires_at):
        """Создание запроса на передачу"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO transfer_requests (nft_id, from_user_id, transfer_code, expires_at)
                VALUES (?, ?, ?, ?)
            ''', (nft_id, from_user_id, transfer_code, expires_at))
            conn.commit()
            return cursor.lastrowid
    
    def get_transfer_by_code(self, code):
        """Получение запроса на передачу по коду"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM transfer_requests 
                WHERE transfer_code = ?
            ''', (code,))
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'nft_id': row[1],
                    'from_user_id': row[2],
                    'to_user_id': row[3],
                    'transfer_code': row[4],
                    'status': row[5],
                    'created_at': row[6],
                    'expires_at': row[7]
                }
            return None
    
    def complete_transfer(self, nft_id, to_user_id, transfer_code=None):
        """Завершение передачи NFT"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Обновляем статус запроса
            if transfer_code:
                cursor.execute('''
                    UPDATE transfer_requests 
                    SET status = 'completed', to_user_id = ?
                    WHERE transfer_code = ?
                ''', (to_user_id, transfer_code))
            
            # Обновляем владельца NFT
            cursor.execute('''
                UPDATE nfts 
                SET user_id = ?, status = 'owned'
                WHERE id = ?
            ''', (to_user_id, nft_id))
            
            conn.commit()
            return True
    
    def check_transfer_code_exists(self, code):
        """Проверка существования кода"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM transfer_requests WHERE transfer_code = ?', (code,))
            return cursor.fetchone() is not None