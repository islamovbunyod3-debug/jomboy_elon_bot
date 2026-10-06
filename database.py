import sqlite3

def init_db():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    # Foydalanuvchilar jadvali
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
    conn.commit()
    conn.close()

def add_invite(user_id: int, username: str, full_name: str):
    """Guruhga odam qo'shganda takliflar sonini oshirish"""
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
    """Foydalanuvchining shaxsiy statistikasini olish"""
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT invited_count, payment_type, payment_details FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row
    return (0, None, None)

def update_payment_details(user_id: int, p_type: str, details: str):
    """To'lov ma'lumotlarini bazaga yozib qo'yish"""
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET payment_type = ?, payment_details = ? WHERE user_id = ?", (p_type, details, user_id))
    conn.commit()
    conn.close()

def get_winners_for_admin():
    """Kamida 50 ta odam qo'shgan va to'lov ma'lumotlarini kiritgan g'oliblarni olish"""
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, username, full_name, invited_count, payment_type, payment_details 
        FROM users 
        WHERE invited_count >= 50 AND payment_details IS NOT NULL
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows

def clear_all_data():
    """Har kuni soat 22:00 dan keyin hamma kirdi-chiqdi va to'lov ma'lumotlarini nolga tenglashtirish"""
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET invited_count = 0, payment_type = NULL, payment_details = NULL")
    conn.commit()
    conn.close()
