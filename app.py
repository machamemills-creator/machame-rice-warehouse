from flask import Flask, request, redirect, render_template_string, session, send_file
import os
import sys
import sqlite3
import time
from datetime import datetime
import urllib.parse

app = Flask(__name__)
app.secret_key = 'machame_secure_warehouse_key_2026'
DB_NAME = "warehouse.db"

def connect_db():
    db = sqlite3.connect(DB_NAME)
    db.row_factory = sqlite3.Row
    return db

def create_tables():
    db = connect_db()
    try:
        db.execute("""
            CREATE TABLE IF NOT EXISTS farmers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                phone TEXT UNIQUE NOT NULL,
                village TEXT NOT NULL
            )
        """)
        
        db.execute("""
            CREATE TABLE IF NOT EXISTS warehouse_stock (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                receipt_no TEXT UNIQUE NOT NULL,
                farmer_id INTEGER,
                rice_variety TEXT NOT NULL,
                bags INTEGER NOT NULL,
                weight_kg REAL NOT NULL,
                storage_fee REAL NOT NULL,
                payment_status TEXT DEFAULT 'Haijalipwa',
                date_received TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (farmer_id) REFERENCES farmers (id)
            )
        """)
        
        try:
            db.execute("ALTER TABLE warehouse_stock ADD COLUMN payment_status TEXT DEFAULT 'Haijalipwa'")
        except:
            pass

        db.execute("""
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                jina_mteja TEXT NOT NULL,
                aina_mpunga TEXT NOT NULL,
                idadi_mifuko INTEGER NOT NULL,
                tarehe TEXT NOT NULL
            )
        """)
        db.commit()
    finally:
        db.close()

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        if username == "admin" and password == "machame2026":
            session['logged_in'] = True
            return redirect("/")
        else:
            return """
            <html>
            <head><title>Hitilafu</title></head>
            <body style="font-family: Arial; text-align: center; padding-top: 50px;">
                <h3 style="color: red;">Jina la mtumiaji au nenosiri si sahihi!</h3>
                <a href="/login" style="color: #2980b9; font-weight: bold; text-decoration: none;">Rudi Jaribu Tena</a>
            </body>
            </html>
            """

    return """
    <html>
    <head>
        <title>Ingia Kwenye Mfumo - Machame Rice Warehouse</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, sans-serif; background-color: #f4f7f6; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .login-box { width: 100%; max-width: 400px; background: white; padding: 40px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border-top: 6px solid #27ae60; }
            h2 { text-align: center; color: #2c3e50; margin-top: 0; }
            p.sub { text-align: center; color: #7f8c8d; font-size: 14px; margin-bottom: 30px; }
            label { font-weight: bold; color: #333; font-size: 14px; }
            input { width: 100%; padding: 12px; margin: 8px 0 20px 0; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; font-size: 14px; }
            button { background-color: #27ae60; color: white; padding: 12px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; width: 100%; font-size: 16px; }
            button:hover { opacity: 0.9; }
        </style>
    </head>
    <body>
        <div class="login-box">
            <h2>🌾 Machame Rice</h2>
            <p class="sub">Weka taarifa zako kuingia ghalani</p>
            <form method="POST">
                <label>Jina la Mtumiaji (Username):</label>
                <input type="text" name="username" required autocomplete="off">
                
                <label>Nenosiri (Password):</label>
                <input type="password" name="password" required>
                
                <button type="submit">Ingia Kwenye Mfumo</button>
            </form>
        </div>
    </body>
    </html>
    """

@app.route("/logout")
def logout():
    session.pop('logged_in', None)
    return redirect("/login")

@app.route("/backup-db")
def backup_db():
    if not session.get('logged_in'):
        return redirect("/login")
    try:
        return send_file(DB_NAME, as_attachment=True)
    except Exception as e:
        return f"Hitilafu ya kupakua backup: {str(e)}"

@app.route("/pay-fee/<int:stock_id>")
def pay_fee(stock_id):
    if not session.get('logged_in'):
        return redirect("/login")
    db = connect_db()
    try:
        db.execute("UPDATE warehouse_stock SET payment_status = 'Imelipwa' WHERE id = ?", (stock_id,))
        db.commit()
    finally:
        db.close()
    return redirect(f"/receipt/{stock_id}")

@app.route("/")
def home():
    if not session.get('logged_in'):
        return redirect("/login")
        
    db = connect_db()
    search_query = request.args.get('q', '').strip()
    
    try:
        stock_summary = db.execute("""
            SELECT rice_variety, 
                   SUM(bags) as total_bags, 
                   SUM(weight_kg) as total_weight,
                   SUM(storage_fee) as total_fees
            FROM warehouse_stock GROUP BY rice_variety
        """).fetchall()
        
        grand_total = db.execute("""
            SELECT SUM(bags) as g_bags, SUM(weight_kg) as g_weight, SUM(storage_fee) as g_fees 
            FROM warehouse_stock
        """).fetchone()

        paid_income = db.execute("SELECT SUM(storage_fee) as p_fee FROM warehouse_stock WHERE payment_status = 'Imelipwa'").fetchone()['p_fee'] or 0
        unpaid_debt = db.execute("SELECT SUM(storage_fee) as u_fee FROM warehouse_stock WHERE payment_status = 'Haijalipwa'").fetchone()['u_fee'] or 0
        
        if search_query:
            recent_receipts = db.execute("""
                SELECT warehouse_stock.*, farmers.full_name, farmers.phone, farmers.village 
                FROM warehouse_stock 
                JOIN farmers ON warehouse_stock.farmer_id = farmers.id 
                WHERE farmers.full_name LIKE ? 
                   OR warehouse_stock.receipt_no LIKE ? 
                   OR farmers.phone LIKE ? 
                   OR warehouse_stock.rice_variety LIKE ?
                ORDER BY warehouse_stock.id DESC
            """, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%', f'%{search_query}%')).fetchall()
        else:
            recent_receipts = db.execute("""
                SELECT warehouse_stock.*, farmers.full_name 
                FROM warehouse_stock 
                JOIN farmers ON warehouse_stock.farmer_id = farmers.id 
                ORDER BY warehouse_stock.id DESC LIMIT 5
            """).fetchall()
        
        farmers_count = db.execute("SELECT COUNT(*) as count FROM farmers").fetchone()["count"]
    finally:
        db.close()

    html = f"""
    <html>
    <head>
        <title>Machame Rice Warehouse - Dashboard</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; margin: 0; padding: 20px; color: #333; }}
            .container {{ max-width: 1150px; margin: auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }}
            .top-header {{ display: flex; justify-content: space-between; align-items: center; }}
            h1 {{ color: #2c3e50; margin: 0; }}
            .top-buttons {{ display: flex; gap: 10px; align-items: center; }}
            .btn-backup {{ background-color: #d35400; color: white; padding: 8px 15px; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 14px; }}
            .btn-backup:hover {{ background-color: #ba4a00; }}
            .btn-logout {{ background-color: #7f8c8d; color: white; padding: 8px 15px; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 14px; }}
            .btn-logout:hover {{ background-color: #616a6b; }}
            .nav-bar {{ display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px; margin: 20px 0; }}
            .nav-buttons {{ display: flex; gap: 10px; flex-wrap: wrap; }}
            .btn {{ background-color: #27ae60; color: white; padding: 10px 18px; text-decoration: none; border-radius: 4px; font-weight: bold; display: inline-block; }}
            .btn-secondary {{ background-color: #2980b9; }}
            .btn-danger {{ background-color: #c0392b; }}
            .btn-report {{ background-color: #8e44ad; color: white; padding: 10px 18px; text-decoration: none; border-radius: 4px; font-weight: bold; display: inline-block; }}
            .btn:hover, .btn-report:hover, .btn-secondary:hover, .btn-danger:hover {{ opacity: 0.9; }}
            .search-box input {{ padding: 10px; width: 250px; border: 1px solid #ccc; border-radius: 4px; font-size: 14px; }}
            .search-box button {{ padding: 10px 15px; background-color: #2c3e50; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; }}
            .cards {{ display: flex; gap: 15px; margin: 25px 0; flex-wrap: wrap; }}
            .card {{ flex: 1; min-width: 200px; background: #e8f8f5; padding: 20px; border-radius: 6px; border-left: 5px solid #27ae60; }}
            .card h3 {{ margin: 0 0 10px 0; color: #16a085; font-size: 13px; }}
            .card p {{ margin: 0; font-size: 20px; font-weight: bold; color: #2c3e50; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; margin-bottom: 30px; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background-color: #f8f9fa; color: #2c3e50; }}
            tr:hover {{ background-color: #f9f9f9; }}
            .total-row {{ background-color: #eafaf1; font-weight: bold; }}
            .badge-paid {{ background-color: #27ae60; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }}
            .badge-unpaid {{ background-color: #e74c3c; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="top-header">
                <div>
                    <h1>🌾 Machame Rice Warehouse</h1>
                    <p style="margin: 5px 0 0 0; color: #7f8c8d;">Mfumo wa Kisasa wa Kusimamia Ghala na Wateja</p>
                </div>
                <div class="top-buttons">
                    <a href="/backup-db" class="btn-backup">💾 Pakua Backup</a>
                    <a href="/logout" class="btn-logout">🔒 Toka (Logout)</a>
                </div>
            </div>
            <hr>
            
            <div class="nav-bar">
                <div class="nav-buttons">
                    <a href="/register" class="btn btn-secondary">➕ Sajili Mteja Mpya</a>
                    <a href="/add-stock" class="btn">📥 Pokea Mpunga na Toa Risiti</a>
                    <a href="/withdraw" class="btn btn-danger">📤 Toa Mpunga Ghalani</a>
                    <a href="/report" class="btn-report">📈 Tazama Ripoti</a>
                </div>
                
                <form class="search-box" method="GET" action="/">
                    <input type="text" name="q" placeholder="Tafuta jina, namba, au risiti..." value="{search_query}">
                    <button type="submit">Tafuta</button>
                </form>
            </div>

            <div class="cards">
                <div class="card">
                    <h3>WATEJA WALIOSAJILIWA</h3>
                    <p>{farmers_count}</p>
                </div>
                <div class="card">
                    <h3>MAGUNIA GHALA</h3>
                    <p>{grand_total['g_bags'] or 0} Magunia</p>
                </div>
                <div class="card" style="border-left-color: #27ae60; background: #eafaf1;">
                    <h3 style="color: #27ae60;">MAPATO YALIYOLIPWA</h3>
                    <p>Tsh {"{:,.2f}".format(paid_income)}</p>
                </div>
                <div class="card" style="border-left-color: #c0392b; background: #fdedec;">
                    <h3 style="color: #c0392b;">MADENI YA UHIFADHI</h3>
                    <p>Tsh {"{:,.2f}".format(unpaid_debt)}</p>
                </div>
            </div>

            <h3>📊 Salio la Mpunga Ghala kwa Kila Aina</h3>
            <table>
                <tr>
                    <th>Aina ya Mpunga (Variety)</th>
                    <th>Jumla ya Magunia</th>
                    <th>Jumla ya Uzito (Kg)</th>
                    <th>Jumla ya Pesa za Uhifadhi (Tsh)</th>
                </tr>
                """ + "".join([f"<tr><td><b>{item['rice_variety']}</b></td><td>{item['total_bags']}</td><td>{item['total_weight']}</td><td>{"{:,.2f}".format(item['total_fees'])}</td></tr>" for item in stock_summary]) + f"""
                {"" if stock_summary else "<tr><td colspan='4' style='text-align: center; color: #777;'>Hakuna mpunga uliopokelewa stoo bado.</td></tr>"}
                
                {f"<tr class='total-row'><td>Jumla Kuu (Grand Total)</td><td>{grand_total['g_bags'] or 0}</td><td>{grand_total['g_weight'] or 0} Kg</td><td>Tsh {{:,.2f}}".format(grand_total['g_fees'] or 0) + "</td></tr>" if stock_summary else ""}
            </table>

            <h3>🧾 Matokeo ya Risiti {f"(Imetafutwa: '{search_query}')" if search_query else "(Mwisho zilizotolewa)"}</h3>
            <table>
                <tr>
                    <th>Namba ya Risiti</th>
                    <th>Jina la Mteja</th>
                    <th>Aina ya Mpunga</th>
                    <th>Magunia</th>
                    <th>Gharama & Malipo</th>
                    <th>Kitendo</th>
                </tr>
                """ + "".join([f"<tr><td>{r['receipt_no']}</td><td>{r['full_name']}</td><td>{r['rice_variety']}</td><td>{r['bags']}</td><td>Tsh {'{:,.2f}'.format(r['storage_fee'])} <br><span class='{'badge-paid' if r['payment_status'] == 'Imelipwa' else 'badge-unpaid'}'>{r['payment_status']}</span></td><td><a href='/receipt/{r['id']}' target='_blank' style='color: #2980b9; text-decoration: none; font-weight: bold;'>Angalia Risiti</a></td></tr>" for r in recent_receipts]) + f"""
                {"" if recent_receipts else "<tr><td colspan='6' style='text-align: center; color: #777;'>Hakuna matokeo yaliyopatikana.</td></tr>"}
            </table>
        </div>
    </body>
    </html>
    """
    return html

@app.route("/register", methods=["GET", "POST"])
def register_farmer():
    if not session.get('logged_in'):
        return redirect("/login")
        
    if request.method == "POST":
        full_name = request.form.get("full_name")
        phone = request.form.get("phone")
        village = request.form.get("village")

        db = connect_db()
        try:
            db.execute("""
                INSERT INTO farmers (full_name, phone, village)
                VALUES (?, ?, ?)
            """, (full_name, phone, village))
            db.commit()
            return redirect("/")
        except Exception as e:
            return f"Hitilafu: {str(e)} <br><a href='/register'>Rudi</a>"
        finally:
            db.close()

    return """
    <html>
    <head>
        <title>Sajili Mteja</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, sans-serif; background-color: #f4f7f6; margin: 0; padding: 40px; }
            .form-box { max-width: 500px; margin: auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
            input { width: 100%; padding: 10px; margin: 8px 0 20px 0; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
            button { background-color: #27ae60; color: white; padding: 12px 20px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; width: 100%; }
            button:hover { opacity: 0.9; }
            .back-link { display: inline-block; margin-top: 15px; color: #2980b9; text-decoration: none; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="form-box">
            <h2>➕ Sajili Mteja / Mkulima Mpya</h2>
            <form method="POST">
                <label><b>Jina Kamili:</b></label>
                <input type="text" name="full_name" required>
                
                <label><b>Namba ya Simu:</b></label>
                <input type="text" name="phone" required>
                
                <label><b>Kijiji / Eneo:</b></label>
                <input type="text" name="village" required>
                
                <button type="submit">Hifadhi Mteja</button>
            </form>
            <a href="/" class="back-link">🏠 Rudi Nyumbani</a>
        </div>
    </body>
    </html>
    """

@app.route("/add-stock", methods=["GET", "POST"])
def add_stock():
    if not session.get('logged_in'):
        return redirect("/login")
        
    db = connect_db()
    if request.method == "POST":
        farmer_id = request.form.get("farmer_id")
        rice_variety = request.form.get("rice_variety")
        bags = int(request.form.get("bags"))
        weight_kg = float(request.form.get("weight_kg"))
        storage_fee = float(request.form.get("storage_fee"))
        payment_status = request.form.get("payment_status")
        
        receipt_no = f"MCH-{int(time.time())}"

        try:
            cursor = db.execute("""
                INSERT INTO warehouse_stock (receipt_no, farmer_id, rice_variety, bags, weight_kg, storage_fee, payment_status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (receipt_no, farmer_id, rice_variety, bags, weight_kg, storage_fee, payment_status))
            db.commit()
            new_id = cursor.lastrowid
            return redirect(f"/receipt/{new_id}")
        except Exception as e:
            return f"Hitilafu: {str(e)} <br><a href='/add-stock'>Rudi</a>"
        finally:
            db.close()

    farmers = db.execute("SELECT * FROM farmers").fetchall()
    db.close()

    farmers_options = "".join([f"<option value='{f['id']}'>{f['full_name']} ({f['village']})</option>" for f in farmers])

    return f"""
    <html>
    <head>
        <title>Pokea Mpunga</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, sans-serif; background-color: #f4f7f6; margin: 0; padding: 40px; }}
            .form-box {{ max-width: 500px; margin: auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }}
            input, select {{ width: 100%; padding: 10px; margin: 8px 0 20px 0; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }}
            button {{ background-color: #27ae60; color: white; padding: 12px 20px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; width: 100%; }}
            button:hover {{ opacity: 0.9; }}
            .back-link {{ display: inline-block; margin-top: 15px; color: #2980b9; text-decoration: none; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="form-box">
            <h2>📥 Pokea Mpunga na Toa Risiti</h2>
            <form method="POST">
                <label><b>Chagua Mteja / Mkulima:</b></label>
                <select name="farmer_id" required>
                    <option value="">-- Chagua Mteja --</option>
                    {farmers_options}
                </select>
                
                <label><b>Aina ya Mpunga (Mf. Mbawambili / Super Kilombero):</b></label>
                <input type="text" name="rice_variety" required>
                
                <label><b>Idadi ya Magunia:</b></label>
                <input type="number" name="bags" required>
                
                <label><b>Uzito wa Jumla (Kg):</b></label>
                <input type="number" step="0.01" name="weight_kg" required>

                <label><b>Gharama za Uhifadhi (Tsh):</b></label>
                <input type="number" step="0.01" name="storage_fee" required>

                <label><b>Hali ya Malipo ya Uhifadhi:</b></label>
                <select name="payment_status" required>
                    <option value="Haijalipwa">🔴 Haijalipwa (Deni)</option>
                    <option value="Imelipwa">🟢 Imelipwa Taslimu</option>
                </select>
                
                <button type="submit">Hifadhi na Toa Risiti</button>
            </form>
            <a href="/" class="back-link">🏠 Rudi Nyumbani</a>
        </div>
    </body>
    </html>
    """

@app.route("/receipt/<int:stock_id>")
def view_receipt(stock_id):
    if not session.get('logged_in'):
        return redirect("/login")
        
    db = connect_db()
    try:
        record = db.execute("""
            SELECT warehouse_stock.*, farmers.full_name, farmers.phone, farmers.village 
            FROM warehouse_stock 
            JOIN farmers ON warehouse_stock.farmer_id = farmers.id 
            WHERE warehouse_stock.id = ?
        """, (stock_id,)).fetchone()
    finally:
        db.close()

    if not record:
        return "Risiti haionekani! <br><a href='/'>Rudi Nyumbani</a>"

    pay_action_btn = ""
    if record['payment_status'] == 'Haijalipwa':
        pay_action_btn = f"<a href='/pay-fee/{stock_id}' style='background-color: #27ae60; color: white; padding: 10px 18px; border-radius: 4px; text-decoration: none; font-weight: bold; display: inline-block; margin-top: 10px;'>💳 Lipia Deni Hili</a>"

    phone_clean = record['phone'].strip()
    if phone_clean.startswith('0'):
        phone_clean = '255' + phone_clean[1:]
    elif not phone_clean.startswith('+'):
        phone_clean = '255' + phone_clean

    whatsapp_msg = (
        f"Habari {record['full_name']}, hii ni risiti yako ya mpunga kutoka Machame Rice Warehouse.\n\n"
        f"📄 Namba ya Risiti: {record['receipt_no']}\n"
        f"🌾 Aina ya Mpunga: {record['rice_variety']}\n"
        f"📦 Magunia: {record['bags']}\n"
        f"⚖️ Uzito: {record['weight_kg']} Kg\n"
        f"💰 Uhifadhi: Tsh {record['storage_fee']:,.2f}\n"
        f"📌 Hali ya Malipo: {record['payment_status']}\n\n"
        f"Asante kwa kuhifadhi nasi!"
    )
    
    encoded_msg = urllib.parse.quote(whatsapp_msg)
    whatsapp_url = f"https://wa.me/{phone_clean}?text={encoded_msg}"

    return f"""
    <html>
    <head>
        <title>Risiti - {record['receipt_no']}</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, sans-serif; background-color: #f4f7f6; margin: 0; padding: 40px; }}
            .receipt-box {{ max-width: 600px; margin: auto; background: white; padding: 40px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border-top: 6px solid #27ae60; }}
            h2 {{ text-align: center; margin-bottom: 5px; color: #2c3e50; }}
            p.sub {{ text-align: center; color: #7f8c8d; margin-top: 0; font-size: 14px; }}
            hr {{ border: 0; border-top: 1px dashed #ccc; margin: 20px 0; }}
            .actions {{ text-align: center; margin-top: 30px; display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; align-items: center; }}
            .btn-print {{ background-color: #2980b9; color: white; padding: 10px 18px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 15px; text-decoration: none; display: inline-block; }}
            .btn-whatsapp {{ background-color: #25d366; color: white; padding: 10px 18px; border-radius: 4px; text-decoration: none; font-weight: bold; font-size: 15px; display: inline-block; }}
            .btn-home {{ color: #27ae60; text-decoration: none; font-weight: bold; font-size: 15px; display: inline-block; }}
            .btn-print:hover, .btn-whatsapp:hover {{ opacity: 0.9; }}
            .badge-paid {{ background-color: #27ae60; color: white; padding: 4px 10px; border-radius: 4px; font-weight: bold; }}
            .badge-unpaid {{ background-color: #e74c3c; color: white; padding: 4px 10px; border-radius: 4px; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="receipt-box">
            <h2>MACHAME RICE WAREHOUSE</h2>
            <p class="sub">Ifakara, Morogoro | Simu: +255 700 000 000</p>
            <hr>
            <p><b>Namba ya Risiti:</b> {record['receipt_no']}</p>
            <p><b>Tarehe:</b> {record['date_received']}</p>
            <hr>
            <h3>Taarifa za Mteja</h3>
            <p><b>Jina la Mteja:</b> {record['full_name']}</p>
            <p><b>Namba ya Simu:</b> {record['phone']}</p>
            <p><b>Kijiji:</b> {record['village']}</p>
            <hr>
            <h3>Taarifa za Mzigo na Malipo</h3>
            <p><b>Aina ya Mpunga:</b> {record['rice_variety']}</p>
            <p><b>Idadi ya Magunia:</b> {record['bags']}</p>
            <p><b>Uzito wa Jumla:</b> {record['weight_kg']} Kg</p>
            <p><b>Gharama za Uhifadhi:</b> Tsh {record['storage_fee']:,.2f}</p>
            <p><b>Hali ya Malipo:</b> <span class="{'badge-paid' if record['payment_status'] == 'Imelipwa' else 'badge-unpaid'}">{record['payment_status']}</span></p>
            <div style="text-align: center; margin-top: 15px;">
                {pay_action_btn}
            </div>
            <hr>
            <p style="text-align: center; font-style: italic; color: #555;">Asante kwa kuhifadhi mpunga wako Machame Rice Warehouse!</p>
            
            <div class="actions">
                <button onclick="window.print()" class="btn-print">🖨️ Chapisha Risiti</button>
                <a href="{whatsapp_url}" target="_blank" class="btn-whatsapp">💬 Tuma WhatsApp</a>
                <a href="/" class="btn-home">🏠 Rudi Nyumbani</a>
            </div>
        </div>
    </body>
    </html>
    """

@app.route("/withdraw", methods=["GET", "POST"])
def withdraw_rice():
    if not session.get('logged_in'):
        return redirect("/login")
        
    db = connect_db()
    if request.method == "POST":
        stock_id = request.form.get("stock_id")
        idadi_mifuko = int(request.form.get("idadi_mifuko"))
        tarehe = datetime.now().strftime("%Y-%m-%d %H:%M")

        try:
            stock_item = db.execute("""
                SELECT warehouse_stock.*, farmers.full_name 
                FROM warehouse_stock 
                JOIN farmers ON warehouse_stock.farmer_id = farmers.id 
                WHERE warehouse_stock.id = ?
            """, (stock_id,)).fetchone()

            if not stock_item:
                return "Mzigo haupatikani! <br><a href='/withdraw'>Rudi</a>"

            current_bags = stock_item["bags"]
            
            if idadi_mifuko > current_bags:
                return f"Idadi unayotaka kutoa ({idadi_mifuko}) ni kubwa kuliko magunia yaliyopo stoo kwa mteja huyu ({current_bags})! <br><a href='/withdraw'>Rudi</a>"

            new_bags = current_bags - idadi_mifuko

            db.execute("""
                INSERT INTO withdrawals (jina_mteja, aina_mpunga, idadi_mifuko, tarehe)
                VALUES (?, ?, ?, ?)
            """, (stock_item["full_name"], stock_item["rice_variety"], idadi_mifuko, tarehe))

            if new_bags == 0:
                db.execute("DELETE FROM warehouse_stock WHERE id = ?", (stock_id,))
            else:
                weight_per_bag = stock_item["weight_kg"] / current_bags
                new_weight = stock_item["weight_kg"] - (idadi_mifuko * weight_per_bag)
                db.execute("""
                    UPDATE warehouse_stock 
                    SET bags = ?, weight_kg = ? 
                    WHERE id = ?
                """, (new_bags, new_weight, stock_id))

            db.commit()
            return redirect("/")
        except Exception as e:
            return f"Hitilafu: {str(e)} <br><a href='/withdraw'>Rudi</a>"
        finally:
            db.close()

    stocks = db.execute("""
        SELECT warehouse_stock.id, warehouse_stock.rice_variety, warehouse_stock.bags, farmers.full_name 
        FROM warehouse_stock 
        JOIN farmers ON warehouse_stock.farmer_id = farmers.id
        WHERE warehouse_stock.bags > 0
    """).fetchall()
    db.close()

    stock_options = "".join([f"<option value='{s['id']}'>{s['full_name']} - {s['rice_variety']} ({s['bags']} magunia ghalani)</option>" for s in stocks])

    return f"""
    <html>
    <head>
        <title>Toa Mpunga Ghalani</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, sans-serif; background-color: #f4f7f6; margin: 0; padding: 40px; }}
            .form-box {{ max-width: 550px; margin: auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }}
            input, select {{ width: 100%; padding: 10px; margin: 8px 0 20px 0; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }}
            button {{ background-color: #c0392b; color: white; padding: 12px 20px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; width: 100%; }}
            button:hover {{ opacity: 0.9; }}
            .back-link {{ display: inline-block; margin-top: 15px; color: #2980b9; text-decoration: none; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="form-box">
            <h2>📤 Toa Mzigo Ghalani (Stock Out)</h2>
            <form method="POST">
                <label><b>Chagua Mzigo wa Mteja Stoo:</b></label>
                <select name="stock_id" required>
                    <option value="">-- Chagua Mzigo --</option>
                    {stock_options}
                </select>

                <label><b>Idadi ya Mifuko Inayotoka:</b></label>
                <input type="number" name="idadi_mifuko" min="1" required>

                <button type="submit">Thibitisha na Toa Mzigo</button>
            </form>
            <a href="/" class="back-link">🏠 Rudi Nyumbani</a>
        </div>
    </body>
    </html>
    """

@app.route("/report")
def warehouse_report():
    if not session.get('logged_in'):
        return redirect("/login")
        
    db = connect_db()
    try:
        stock_summary = db.execute("""
            SELECT rice_variety, 
                   SUM(bags) as total_bags, 
                   SUM(weight_kg) as total_weight,
                   SUM(storage_fee) as total_fees
            FROM warehouse_stock GROUP BY rice_variety
        """).fetchall()
        
        grand_total = db.execute("""
            SELECT SUM(bags) as g_bags, SUM(weight_kg) as g_weight, SUM(storage_fee) as g_fees 
            FROM warehouse_stock
        """).fetchone()

        paid_income = db.execute("SELECT SUM(storage_fee) as p_fee FROM warehouse_stock WHERE payment_status = 'Imelipwa'").fetchone()['p_fee'] or 0
        unpaid_debt = db.execute("SELECT SUM(storage_fee) as u_fee FROM warehouse_stock WHERE payment_status = 'Haijalipwa'").fetchone()['u_fee'] or 0
        
        withdrawals = db.execute("SELECT * FROM withdrawals ORDER BY id DESC").fetchall()
        farmers_count = db.execute("SELECT COUNT(*) as count FROM farmers").fetchone()["count"]
    finally:
        db.close()

    return f"""
    <html>
    <head>
        <title>Ripoti ya Machame Rice Warehouse</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, sans-serif; background-color: #f4f7f6; margin: 0; padding: 30px; color: #333; }}
            .container {{ max-width: 1000px; margin: auto; background: white; padding: 40px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border-top: 6px solid #8e44ad; }}
            h1, h2 {{ color: #2c3e50; text-align: center; }}
            p.sub {{ text-align: center; color: #7f8c8d; margin-top: -10px; margin-bottom: 30px; }}
            hr {{ border: 0; border-top: 1px solid #ddd; margin: 25px 0; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; margin-bottom: 30px; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background-color: #f8f9fa; color: #2c3e50; }}
            tr:hover {{ background-color: #f9f9f9; }}
            .total-row {{ background-color: #eafaf1; font-weight: bold; }}
            .summary-box {{ display: flex; gap: 15px; margin-bottom: 20px; flex-wrap: wrap; }}
            .s-card {{ flex: 1; min-width: 200px; background: #f8f9fa; padding: 15px; border-radius: 6px; border: 1px solid #e1e4e8; text-align: center; }}
            .s-card h4 {{ margin: 0; color: #7f8c8d; font-size: 13px; }}
            .s-card p {{ margin: 5px 0 0 0; font-size: 18px; font-weight: bold; color: #2c3e50; }}
            .actions {{ text-align: center; margin-top: 30px; }}
            .btn-print {{ background-color: #8e44ad; color: white; padding: 10px 25px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 16px; text-decoration: none; }}
            .btn-home {{ display: inline-block; margin-left: 15px; color: #27ae60; text-decoration: none; font-weight: bold; font-size: 16px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>📈 RIPOTI YA UENDESHAJI - MACHAME RICE WAREHOUSE</h2>
            <p class="sub">Ifakara, Morogoro | Taarifa Rasmi ya Ghala</p>
            <hr>

            <div class="summary-box">
                <div class="s-card">
                    <h4>Jumla ya Wateja</h4>
                    <p>{farmers_count}</p>
                </div>
                <div class="s-card">
                    <h4>Magunia ya Mpunga</h4>
                    <p>{grand_total['g_bags'] or 0} Magunia</p>
                </div>
                <div class="s-card" style="border-top: 4px solid #27ae60;">
                    <h4>Mapato Yaliyolipwa</h4>
                    <p style="color: #27ae60;">Tsh {"{:,.2f}".format(paid_income)}</p>
                </div>
                <div class="s-card" style="border-top: 4px solid #c0392b;">
                    <h4>Madeni ya Uhifadhi</h4>
                    <p style="color: #c0392b;">Tsh {"{:,.2f}".format(unpaid_debt)}</p>
                </div>
            </div>

            <h3>📊 Hali ya Salio la Mpunga Ghalani kwa Sasa</h3>
            <table>
                <tr>
                    <th>Aina ya Mpunga (Variety)</th>
                    <th>Jumla ya Magunia</th>
                    <th>Uzito wa Jumla (Kg)</th>
                    <th>Jumla ya Ada (Tsh)</th>
                </tr>
                {"".join([f"<tr><td><b>{item['rice_variety']}</b></td><td>{item['total_bags']}</td><td>{item['total_weight']} Kg</td><td>{'{:,.2f}'.format(item['total_fees'])}</td></tr>" for item in stock_summary]) or "<tr><td colspan='4' style='text-align: center; color: #777;'>Hakuna mzigo stoo kwa sasa.</td></tr>"}
                {f"<tr class='total-row'><td>Jumla Kuu</td><td>{grand_total['g_bags'] or 0}</td><td>{grand_total['g_weight'] or 0} Kg</td><td>Tsh {('{:,.2f}'.format(grand_total['g_fees'] or 0))}</td></tr>" if stock_summary else ""}
            </table>

            <h3>📤 Historia ya Mpunga Uliotoka Ghalani (Withdrawals)</h3>
            <table>
                <tr>
                    <th>Jina la Mteja</th>
                    <th>Aina ya Mpunga</th>
                    <th>Idadi ya Mifuko Iliyotoka</th>
                    <th>Tarehe na Wakati</th>
                </tr>
                {"".join([f"<tr><td>{w['jina_mteja']}</td><td>{w['aina_mpunga']}</td><td>{w['idadi_mifuko']}</td><td>{w['tarehe']}</td></tr>" for w in withdrawals]) or "<tr><td colspan='4' style='text-align: center; color: #777;'>Hakuna kumbukumbu za kutoa mpunga bado.</td></tr>"}
            </table>

            <div class="actions">
                <button onclick="window.print()" class="btn-print">🖨️ Chapisha Ripoti</button>
                <a href="/" class="btn-home">🏠 Rudi Nyumbani</a>
            </div>
        </div>
    </body>
    </html>
    """

if __name__ == '__main__':
    # Hii inasaidia mfumo kujua njia za templates na database ukiwa nje ya Python
    if getattr(sys, 'frozen', False):
        template_folder = os.path.join(sys._MEIPASS, 'templates')
        static_folder = os.path.join(sys._MEIPASS, 'static')
        app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
    
    # Tunazima debug=True ili kuzuia lile kosa la WinError 10038 kwenye .exe
    app.run(host='127.0.0.1', port=5000, debug=False)