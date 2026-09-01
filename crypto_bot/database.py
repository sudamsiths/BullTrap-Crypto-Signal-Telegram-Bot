import sqlite3
import logging

# Set up logging
logging.basicConfig(
    filename='bot_activity.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def init_db():
    conn = sqlite3.connect('crypto_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            symbol TEXT,
            signal_type TEXT,
            price REAL,
            stop_loss REAL,
            take_profit REAL
        )
    ''')
    conn.commit()
    conn.close()
    logging.info("Database initialized successfully.")

def save_signal(symbol, signal_type, price, sl, tp):
    conn = sqlite3.connect('crypto_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO signals (symbol, signal_type, price, stop_loss, take_profit)
        VALUES (?, ?, ?, ?, ?)
    ''', (symbol, signal_type, price, sl, tp))
    conn.commit()
    conn.close()
    logging.info(f"Signal saved: {symbol} - {signal_type} at {price}")