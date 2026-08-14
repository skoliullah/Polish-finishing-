import os
import sqlite3
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
DB_NAME = "database.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Settings Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Work Entries Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS work_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            code TEXT,
            weight REAL,
            model TEXT,
            rate REAL,
            amount REAL,
            locked INTEGER DEFAULT 1
        )
    ''')
    
    # Expense Entries Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            description TEXT,
            amount REAL,
            locked INTEGER DEFAULT 1
        )
    ''')

    # Defaults
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('master_lock', 'true')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('rates_locked', 'false')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('calcutta_rate', '0')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('laser_rate', '0')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('gpc_total_packets', '0')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('gpc_total_cost', '0')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('gpc_used_packets', '[]')")
    
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/data', methods=['GET'])
def get_all_data():
    conn = get_db()
    cursor = conn.cursor()

    # Get settings
    cursor.execute("SELECT * FROM settings")
    settings_rows = cursor.fetchall()
    settings = {row['key']: row['value'] for row in settings_rows}

    # Get work
    cursor.execute("SELECT * FROM work_entries ORDER BY id DESC")
    work_entries = [dict(row) for row in cursor.fetchall()]

    # Get expenses
    cursor.execute("SELECT * FROM expenses ORDER BY id DESC")
    expenses = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return jsonify({
        "settings": {
            "masterLock": settings.get('master_lock') == 'true',
            "ratesLocked": settings.get('rates_locked') == 'true',
            "calcuttaRate": float(settings.get('calcutta_rate', 0)),
            "laserRate": float(settings.get('laser_rate', 0)),
            "gpc": {
                "totalPackets": int(settings.get('gpc_total_packets', 0)),
                "totalCost": float(settings.get('gpc_total_cost', 0)),
                "usedPackets": json.loads(settings.get('gpc_used_packets', '[]'))
            }
        },
        "workEntries": work_entries,
        "expenses": expenses
    })

@app.route('/api/settings/master-lock', methods=['POST'])
def toggle_master_lock():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key='master_lock'")
    curr = cursor.fetchone()['value']
    new_val = 'false' if curr == 'true' else 'true'
    cursor.execute("UPDATE settings SET value=? WHERE key='master_lock'", (new_val,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "masterLock": new_val == 'true'})

@app.route('/api/rates', methods=['POST'])
def update_rates():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("UPDATE settings SET value=? WHERE key='rates_locked'", ('true' if data['locked'] else 'false',))
    cursor.execute("UPDATE settings SET value=? WHERE key='calcutta_rate'", (str(data['calcuttaRate']),))
    cursor.execute("UPDATE settings SET value=? WHERE key='laser_rate'", (str(data['laserRate']),))
    
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/work', methods=['POST'])
def add_work():
    data = request.json
    today_str = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO work_entries (date, code, weight, model, rate, amount, locked)
        VALUES (?, ?, ?, ?, ?, ?, 1)
    ''', (today_str, data['code'], data['weight'], data['model'], data['rate'], data['amount']))
    
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/expense', methods=['POST'])
def add_expense():
    data = request.json
    today_str = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO expenses (date, description, amount, locked)
        VALUES (?, ?, ?, 1)
    ''', (today_str, data['description'], data['amount']))
    
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/gpc', methods=['POST'])
def update_gpc():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("UPDATE settings SET value=? WHERE key='gpc_total_packets'", (str(data['totalPackets']),))
    cursor.execute("UPDATE settings SET value=? WHERE key='gpc_total_cost'", (str(data['totalCost']),))
    cursor.execute("UPDATE settings SET value=? WHERE key='gpc_used_packets'", (json.dumps(data['usedPackets']),))
    
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/toggle-lock', methods=['POST'])
def toggle_item_lock():
    data = request.json
    target = data['type']  # 'work' or 'expense'
    item_id = data['id']
    
    conn = get_db()
    cursor = conn.cursor()
    
    table = "work_entries" if target == "work" else "expenses"
    cursor.execute(f"SELECT locked FROM {table} WHERE id=?", (item_id,))
    curr = cursor.fetchone()['locked']
    new_val = 0 if curr == 1 else 1
    
    cursor.execute(f"UPDATE {table} SET locked=? WHERE id=?", (new_val, item_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/delete', methods=['POST'])
def delete_item():
    data = request.json
    target = data['type']
    item_id = data['id']
    
    conn = get_db()
    cursor = conn.cursor()
    
    table = "work_entries" if target == "work" else "expenses"
    cursor.execute(f"DELETE FROM {table} WHERE id=?", (item_id,))
    
    conn.commit()
    conn.close()
    return jsonify({"success": True})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
