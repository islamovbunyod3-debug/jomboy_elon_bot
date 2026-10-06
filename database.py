import sqlite3

def init_db():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    # 1. Kundalik kirdi-chiqdi jadvali
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            invited_count INTEGER DEFAULT 0,
            payment_type TEXT DEFAULT NULL,
            payment_details TEXT DEFAULT NULL
        )
    """)
    # 2. To'lov kutayotgan g'oliblar arxivi (Admin boshqarishi uchun)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            full_name TEXT,
            amount INTEGER,
            payment_type TEXT,
            payment_details TEXT,
            status TEXT DEFAULT 'Kutilmoqda'
        )
    """)
    conn.commit()
    conn.close()

def add_invite(user_id: int, username: str, full_name: str):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (user_id, username, full_name, invited_count)
        VALUES (?, ?, ?, 1)
        ON CONFLICT(user_id) DO UPDATE SET invited_count = invited_count + 1
    """, (user_id, username, full_name))
    conn.commit()
    conn.close()

def get_user_stats(user_id: int):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT invited_count, payment_type, payment_details FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row if row else (0, None, None)

def update_payment_details(user_id: int, p_type: str, details: str):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET payment_type = ?, payment_details = ? WHERE user_id = ?", (p_type, details, user_id))
    conn.commit()
    conn.close()

def transfer_to_payouts_and_clear():
    """Soat 22:00 da hamma kirdi-chiqdini tozalab, g'oliblarni to'lov ro'yxatiga o'tkazish"""
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    
    # 50 tadan o'tgan va karta/tel kiritganlarni olamiz
    cursor.execute("SELECT user_id, full_name, invited_count, payment_type, payment_details FROM users WHERE invited_count >= 50 AND payment_details IS NOT NULL")
    winners = cursor.fetchall()
    
    for user_id, full_name, count, p_type, p_details in winners:
        amount = (count // 50) * 10000
        cursor.execute("""
            INSERT INTO payouts (user_id, full_name, amount, payment_type, payment_details)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, full_name, amount, p_type, p_details))
        
    # Kirdi-chiqdi tarixini butunlay tozalash (0 qilib qo'yish)
    cursor.execute("UPDATE users SET invited_count = 0, payment_type = NULL, payment_details = NULL")
    conn.commit()
    conn.close()
    return winners

def get_pending_payouts():
    """Admin to'lashi kerak bo'lgan kutilayotgan barcha to'lovlarni olish"""
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, full_name, amount, payment_type, payment_details FROM payouts WHERE status = 'Kutilmoqda'")
    rows = cursor.fetchall()
    conn.close()
    return rows

def complete_payout(payout_id: int):
    """To'lov bajarilganidan keyin statusni o'zgartirish va foydalanuvchi ID sini qaytarish"""
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, amount FROM payouts WHERE id = ?", (payout_id,))
    res = cursor.fetchone()
    if res:
        cursor.execute("UPDATE payouts SET status = 'Toʻlandi' WHERE id = ?", (payout_id,))
        conn.commit()
        conn.close()
        return res  # (user_id, amount) qaytadi
    conn.close()
    return None
