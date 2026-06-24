"""
Premium Dark Mode App — CustomTkinter + MySQL/SQLite + bcrypt
=============================================================
โครงสร้าง OOP แบบ Multi-Page System พร้อมระบบ Login, Dashboard, SQL Table
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
import pymysql
import bcrypt
import threading
from datetime import datetime

# ────────────────────────── THEME CONFIG ──────────────────────────

class Theme:
    BG_MAIN       = "#111315"   # พื้นหลังฝั่งขวา (main content)
    BG_SIDEBAR    = "#1A1D20"   # แถบเมนูซ้าย
    BG_CARD       = "#212529"   # กล่อง card / container
    BG_INPUT      = "#2C3035"   # ช่องกรอกข้อมูล
    BG_TABLE_ALT  = "#1C1F23"   # แถวสลับใน table
    BG_HOVER      = "#2A2D32"   # สีเมื่อ hover ปุ่ม

    ACCENT_BLUE   = "#00B0FF"   # ไฮไลต์หลัก (ปุ่ม active)
    ACCENT_GREEN  = "#00E676"   # สถานะ / online
    ACCENT_RED    = "#FF5252"   # error / offline
    ACCENT_ORANGE = "#FF9100"   # warning

    TEXT_PRIMARY  = "#E8EAED"   # ข้อความหลัก
    TEXT_SECONDARY= "#9AA0A6"   # ข้อความรอง
    TEXT_DISABLED = "#5F6368"   # disabled

    FONT_MAIN     = "Segoe UI"
    RADIUS        = 10
    RADIUS_SM     = 6


# ────────────────────────── DATABASE CONFIG ──────────────────────────

DB_CONFIG = {
    "host":     "localhost",
    "port":     3306,
    "user":     "root",
    "password": "1234",  # ← เปลี่ยนตามจริง
    "database": "myapp_db",
    "charset":  "utf8mb4",
}

# สำหรับ demo offline (ใช้ SQLite แทนถ้า MySQL ไม่ได้ติดตั้ง)
USE_SQLITE_FALLBACK = True   # เปลี่ยนเป็น False เมื่อใช้ MySQL จริง


# ────────────────────────── DATABASE MANAGER ──────────────────────────

class DatabaseManager:
    """จัดการการเชื่อมต่อและคำสั่ง SQL แบบรวมศูนย์"""

    def __init__(self):
        self.conn = None
        self.is_connected = False
        self._use_sqlite = USE_SQLITE_FALLBACK

    # ── เชื่อมต่อ ──────────────────────────────────────────────────

    def connect(self) -> bool:
        try:
            if self._use_sqlite:
                import sqlite3
                self.conn = sqlite3.connect(":memory:", check_same_thread=False)
                self._seed_sqlite()
            else:
                self.conn = pymysql.connect(**DB_CONFIG, autocommit=True)
            self.is_connected = True
            return True
        except Exception as e:
            print(f"[DB] Connection error: {e}")
            self.is_connected = False
            return False

    def disconnect(self):
        if self.conn:
            self.conn.close()
            self.is_connected = False

    # ── Seed ข้อมูลตัวอย่าง (SQLite) ─────────────────────────────

    def _seed_sqlite(self):
        """สร้างตารางและข้อมูลตัวอย่างสำหรับ Demo"""
        cur = self.conn.cursor()
        # ตาราง users
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                role     TEXT DEFAULT 'user',
                created  TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # ตาราง products
        cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                name     TEXT,
                category TEXT,
                price    REAL,
                stock    INTEGER,
                status   TEXT DEFAULT 'active'
            )
        """)

        # สร้าง admin user ด้วย bcrypt (password = "admin1234")
        hashed = bcrypt.hashpw(b"admin1234", bcrypt.gensalt()).decode()
        cur.execute(
            "INSERT OR IGNORE INTO users (username, password, role) VALUES (?,?,?)",
            ("admin", hashed, "admin")
        )
        # ข้อมูลสินค้าตัวอย่าง
        products = [
            ("MacBook Pro M3",    "Laptop",    89900, 12, "active"),
            ("iPhone 15 Pro",     "Phone",     49900, 30, "active"),
            ("iPad Air",          "Tablet",    28900, 18, "active"),
            ("Sony WH-1000XM5",  "Audio",      12900,  8, "active"),
            ("Samsung 4K OLED",   "Display",   45000,  5, "active"),
            ("Logitech MX Keys",  "Keyboard",   5490, 25, "low_stock"),
            ("Dell XPS 15",       "Laptop",    79900,  3, "low_stock"),
            ("Apple Watch S9",    "Wearable",  16900, 22, "active"),
            ("Anker USB-C Hub",   "Accessory",  2390, 50, "active"),
            ("Razer DeathAdder",  "Mouse",      3490,  0, "out_of_stock"),
        ]
        cur.executemany(
            "INSERT OR IGNORE INTO products (name, category, price, stock, status) VALUES (?,?,?,?,?)",
            products
        )
        self.conn.commit()

    # ── Auth ───────────────────────────────────────────────────────

    def verify_login(self, username: str, password: str) -> dict | None:
        """คืน dict ข้อมูลผู้ใช้หากผ่านการตรวจสอบ"""
        try:
            cur = self.conn.cursor()
            if self._use_sqlite:
                cur.execute(
                    "SELECT id, username, password, role FROM users WHERE username=?",
                    (username,)
                )
            else:
                cur.execute(
                    "SELECT id, username, password, role FROM users WHERE username=%s",
                    (username,)
                )
            row = cur.fetchone()
            if row and bcrypt.checkpw(password.encode(), row[2].encode()):
                return {"id": row[0], "username": row[1], "role": row[3]}
        except Exception as e:
            print(f"[DB] Login error: {e}")
        return None

    def create_user(self, username: str, password: str, role: str = "user") -> bool:
        """สร้างผู้ใช้ใหม่พร้อม hash password"""
        try:
            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            cur = self.conn.cursor()
            if self._use_sqlite:
                cur.execute(
                    "INSERT INTO users (username, password, role) VALUES (?,?,?)",
                    (username, hashed, role)
                )
            else:
                cur.execute(
                    "INSERT INTO users (username, password, role) VALUES (%s,%s,%s)",
                    (username, hashed, role)
                )
            self.conn.commit()
            return True
        except Exception as e:
            print(f"[DB] Create user error: {e}")
            return False

    # ── Data Queries ───────────────────────────────────────────────

    def fetch_products(self, search: str = "") -> list[tuple]:
        try:
            cur = self.conn.cursor()
            if self._use_sqlite:
                q = "SELECT id, name, category, price, stock, status FROM products WHERE name LIKE ?"
                cur.execute(q, (f"%{search}%",))
            else:
                q = "SELECT id, name, category, price, stock, status FROM products WHERE name LIKE %s"
                cur.execute(q, (f"%{search}%",))
            return cur.fetchall()
        except Exception as e:
            print(f"[DB] Fetch error: {e}")
            return []

    def get_stats(self) -> dict:
        """ดึงสถิติสำหรับ Dashboard"""
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT COUNT(*) FROM products")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM products WHERE status='active'")
            active = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM products WHERE status='out_of_stock'")
            oos = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM users")
            users = cur.fetchone()[0]
            return {"total": total, "active": active, "out_of_stock": oos, "users": users}
        except:
            return {"total": 0, "active": 0, "out_of_stock": 0, "users": 0}


# ────────────────────────── REUSABLE WIDGETS ──────────────────────────

class Card(ctk.CTkFrame):
    """กล่อง Container สไตล์ Card"""
    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.RADIUS,
            **kwargs
        )


class SectionLabel(ctk.CTkLabel):
    def __init__(self, master, text, **kwargs):
        super().__init__(
            master, text=text,
            font=(Theme.FONT_MAIN, 11, "bold"),
            text_color=Theme.TEXT_SECONDARY,
            **kwargs
        )


class PrimaryButton(ctk.CTkButton):
    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=Theme.ACCENT_BLUE,
            hover_color="#0090D6",
            text_color="#000000",
            font=(Theme.FONT_MAIN, 13, "bold"),
            corner_radius=Theme.RADIUS_SM,
            height=40,
            **kwargs
        )


class StatusBadge(ctk.CTkLabel):
    STATUS_MAP = {
        "active":        (Theme.ACCENT_GREEN, "#0D2818"),
        "low_stock":     (Theme.ACCENT_ORANGE, "#2A1A00"),
        "out_of_stock":  (Theme.ACCENT_RED, "#2A0A0A"),
    }
    def __init__(self, master, status: str, **kwargs):
        fg, bg = self.STATUS_MAP.get(status, (Theme.TEXT_SECONDARY, Theme.BG_CARD))
        super().__init__(
            master,
            text=status.replace("_", " ").title(),
            text_color=fg,
            fg_color=bg,
            corner_radius=4,
            font=(Theme.FONT_MAIN, 10, "bold"),
            padx=6, pady=2,
            **kwargs
        )


# ────────────────────────── PAGE: LOGIN ──────────────────────────

class LoginWindow(ctk.CTk):
    """หน้าต่าง Login แยกต่างหาก ก่อนเข้าแอปหลัก"""

    def __init__(self, db: DatabaseManager):
        super().__init__()
        self.db = db
        self.result_user = None   # เก็บข้อมูล user ที่ล็อกอินสำเร็จ

        # ── Window setup ────────────────────────────────────
        self.title("App — Login")
        self.geometry(self._center(500, 650))
        self.resizable(False, False)
        self.configure(fg_color=Theme.BG_MAIN)
        ctk.set_appearance_mode("dark")

        self._build_ui()

    def _center(self, w: int, h: int) -> str:
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        return f"{w}x{h}+{x}+{y}"

    def _build_ui(self):
        # ── Logo zone ────────────────────────────────────────
        logo_frame = ctk.CTkFrame(self, fg_color="transparent")
        logo_frame.pack(pady=(60, 0))

        # ไอคอนวงกลมแทนโลโก้
        icon_canvas = tk.Canvas(
            logo_frame, width=72, height=72,
            bg=Theme.BG_MAIN, highlightthickness=0
        )
        icon_canvas.pack()
        icon_canvas.create_oval(
            4, 4, 68, 68,
            fill=Theme.BG_CARD, outline=Theme.ACCENT_BLUE, width=2
        )
        icon_canvas.create_text(
            36, 36, text="⬡", fill=Theme.ACCENT_BLUE,
            font=("Segoe UI", 26, "bold")
        )

        ctk.CTkLabel(
            logo_frame, text="App",
            font=(Theme.FONT_MAIN, 22, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).pack(pady=(12, 0))

        ctk.CTkLabel(
            logo_frame, text="Sign in to your account",
            font=(Theme.FONT_MAIN, 12),
            text_color=Theme.TEXT_SECONDARY
        ).pack()

        # ── Form card ────────────────────────────────────────
        card = Card(self, width=340)
        card.pack(pady=30, padx=40, fill="x")
        card.pack_propagate(False)
        card.configure(height=260)

        form = ctk.CTkFrame(card, fg_color="transparent")
        form.pack(padx=28, pady=28, fill="x")

        # Username
        SectionLabel(form, "USERNAME").pack(anchor="w", pady=(0, 4))
        self.entry_user = ctk.CTkEntry(
            form, placeholder_text="Enter username",
            height=40, corner_radius=Theme.RADIUS_SM,
            fg_color=Theme.BG_INPUT, border_color=Theme.BG_HOVER,
            text_color=Theme.TEXT_PRIMARY,
            font=(Theme.FONT_MAIN, 13)
        )
        self.entry_user.pack(fill="x")

        # Password
        SectionLabel(form, "PASSWORD").pack(anchor="w", pady=(16, 4))
        self.entry_pass = ctk.CTkEntry(
            form, placeholder_text="Enter password",
            show="●", height=40, corner_radius=Theme.RADIUS_SM,
            fg_color=Theme.BG_INPUT, border_color=Theme.BG_HOVER,
            text_color=Theme.TEXT_PRIMARY,
            font=(Theme.FONT_MAIN, 13)
        )
        self.entry_pass.pack(fill="x")

        # Error label
        self.lbl_error = ctk.CTkLabel(
            self, text="", text_color=Theme.ACCENT_RED,
            font=(Theme.FONT_MAIN, 12)
        )
        self.lbl_error.pack()

        # Login button
        self.btn_login = PrimaryButton(
            self, text="Sign In",
            command=self._do_login, width=340
        )
        self.btn_login.pack(pady=(4, 0))

        # DB status
        status_text = "● SQLite Demo" if USE_SQLITE_FALLBACK else "● MySQL"
        status_color = Theme.ACCENT_GREEN if USE_SQLITE_FALLBACK else Theme.ACCENT_BLUE
        ctk.CTkLabel(
            self, text=status_text,
            text_color=status_color,
            font=(Theme.FONT_MAIN, 10)
        ).pack(pady=(20, 0))

        ctk.CTkLabel(
            self,
            text="Default: admin / admin1234",
            text_color=Theme.TEXT_DISABLED,
            font=(Theme.FONT_MAIN, 10)
        ).pack()

        # bind Enter key
        self.entry_pass.bind("<Return>", lambda e: self._do_login())
        self.entry_user.bind("<Return>", lambda e: self.entry_pass.focus())

    def _do_login(self):
        username = self.entry_user.get().strip()
        password = self.entry_pass.get()

        if not username or not password:
            self.lbl_error.configure(text="⚠  Please fill in all fields")
            return

        self.btn_login.configure(state="disabled", text="Signing in…")
        self.update()

        user = self.db.verify_login(username, password)
        if user:
            self.result_user = user
            self.destroy()           # ปิด Login แล้วเปิด Dashboard
        else:
            self.btn_login.configure(state="normal", text="Sign In")
            self.lbl_error.configure(text="✗  Invalid username or password")


# ────────────────────────── PAGE: DASHBOARD ──────────────────────────

class DashboardPage(ctk.CTkFrame):
    def __init__(self, master, db: DatabaseManager, user: dict):
        super().__init__(master, fg_color=Theme.BG_MAIN)
        self.db = db
        self.user = user
        self._build()

    def _build(self):
        # ── Header ───────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=28, pady=(28, 0))

        ctk.CTkLabel(
            header, text="Dashboard",
            font=(Theme.FONT_MAIN, 22, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).pack(side="left")

        now = datetime.now().strftime("%d %b %Y, %H:%M")
        ctk.CTkLabel(
            header, text=now,
            font=(Theme.FONT_MAIN, 12),
            text_color=Theme.TEXT_SECONDARY
        ).pack(side="right", pady=(6, 0))

        # ── DB Connection status ──────────────────────────────
        conn_card = Card(self)
        conn_card.pack(fill="x", padx=28, pady=(16, 0))

        row = ctk.CTkFrame(conn_card, fg_color="transparent")
        row.pack(padx=20, pady=14, fill="x")

        dot_color = Theme.ACCENT_GREEN if self.db.is_connected else Theme.ACCENT_RED
        dot_text  = "● Connected" if self.db.is_connected else "● Disconnected"
        db_label  = "SQLite (Demo Mode)" if USE_SQLITE_FALLBACK else "MySQL"

        ctk.CTkLabel(
            row, text="Database Status",
            font=(Theme.FONT_MAIN, 13, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).pack(side="left")

        right_row = ctk.CTkFrame(row, fg_color="transparent")
        right_row.pack(side="right")
        ctk.CTkLabel(
            right_row, text=dot_text,
            text_color=dot_color,
            font=(Theme.FONT_MAIN, 12, "bold")
        ).pack(side="left", padx=(0, 12))
        ctk.CTkLabel(
            right_row, text=f"[{db_label}]",
            text_color=Theme.TEXT_DISABLED,
            font=(Theme.FONT_MAIN, 11)
        ).pack(side="left")

        # ── Stats cards ───────────────────────────────────────
        stats = self.db.get_stats()
        stat_data = [
            ("📦  Total Products", str(stats["total"]),   Theme.ACCENT_BLUE),
            ("✅  Active",          str(stats["active"]),  Theme.ACCENT_GREEN),
            ("🚫  Out of Stock",    str(stats["out_of_stock"]), Theme.ACCENT_RED),
            ("👤  Users",           str(stats["users"]),   Theme.ACCENT_ORANGE),
        ]

        stat_frame = ctk.CTkFrame(self, fg_color="transparent")
        stat_frame.pack(fill="x", padx=28, pady=(16, 0))
        stat_frame.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="stat")

        for i, (label, value, color) in enumerate(stat_data):
            card = Card(stat_frame)
            card.grid(row=0, column=i, padx=(0, 10 if i < 3 else 0), sticky="ew")
            ctk.CTkLabel(
                card, text=value,
                font=(Theme.FONT_MAIN, 32, "bold"),
                text_color=color
            ).pack(pady=(16, 0))
            ctk.CTkLabel(
                card, text=label,
                font=(Theme.FONT_MAIN, 11),
                text_color=Theme.TEXT_SECONDARY
            ).pack(pady=(2, 16))

        # ── User info card ────────────────────────────────────
        user_card = Card(self)
        user_card.pack(fill="x", padx=28, pady=(16, 0))

        u_row = ctk.CTkFrame(user_card, fg_color="transparent")
        u_row.pack(padx=20, pady=16, fill="x")

        ctk.CTkLabel(
            u_row, text="👤  Logged in as",
            font=(Theme.FONT_MAIN, 12),
            text_color=Theme.TEXT_SECONDARY
        ).pack(side="left")

        ctk.CTkLabel(
            u_row,
            text=f"  {self.user['username']}  ",
            font=(Theme.FONT_MAIN, 13, "bold"),
            text_color=Theme.ACCENT_BLUE,
            fg_color=Theme.BG_INPUT,
            corner_radius=4
        ).pack(side="left", padx=8)

        ctk.CTkLabel(
            u_row, text=f"Role: {self.user['role'].upper()}",
            font=(Theme.FONT_MAIN, 11),
            text_color=Theme.TEXT_DISABLED
        ).pack(side="left")

        # ── Quick tips ────────────────────────────────────────
        tip_card = Card(self)
        tip_card.pack(fill="x", padx=28, pady=(16, 28))

        tips = [
            "💡  ไปที่เมนู SQL Database เพื่อค้นหาและดูข้อมูลสินค้า",
            "🔐  Password ถูกเข้ารหัสด้วย bcrypt (cost=12) ก่อนบันทึก",
            "📡  รองรับ MySQL จริง: ปิด USE_SQLITE_FALLBACK ในโค้ด",
        ]
        for tip in tips:
            ctk.CTkLabel(
                tip_card, text=tip,
                font=(Theme.FONT_MAIN, 12),
                text_color=Theme.TEXT_SECONDARY,
                anchor="w"
            ).pack(anchor="w", padx=20, pady=(10, 0))

        ctk.CTkLabel(tip_card, text="").pack(pady=6)


# ────────────────────────── PAGE: SQL DATABASE ──────────────────────────

class SQLPage(ctk.CTkFrame):
    COLUMNS = ("ID", "Name", "Category", "Price (฿)", "Stock", "Status")

    def __init__(self, master, db: DatabaseManager):
        super().__init__(master, fg_color=Theme.BG_MAIN)
        self.db = db
        self._all_rows: list[tuple] = []
        self._build()
        self._load_data()

    def _build(self):
        # ── Header ───────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=28, pady=(28, 0))

        ctk.CTkLabel(
            header, text="SQL Database",
            font=(Theme.FONT_MAIN, 22, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).pack(side="left")

        # ── Toolbar ───────────────────────────────────────────
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=28, pady=(14, 0))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search_change)

        self.entry_search = ctk.CTkEntry(
            toolbar,
            textvariable=self.search_var,
            placeholder_text="🔍  Search by name…",
            height=38, corner_radius=Theme.RADIUS_SM,
            fg_color=Theme.BG_INPUT, border_color=Theme.BG_HOVER,
            text_color=Theme.TEXT_PRIMARY,
            font=(Theme.FONT_MAIN, 13),
            width=300
        )
        self.entry_search.pack(side="left")

        PrimaryButton(
            toolbar, text="Refresh",
            command=self._load_data, width=100
        ).pack(side="left", padx=(10, 0))

        self.lbl_count = ctk.CTkLabel(
            toolbar, text="",
            text_color=Theme.TEXT_SECONDARY,
            font=(Theme.FONT_MAIN, 12)
        )
        self.lbl_count.pack(side="right")

        # ── Table ─────────────────────────────────────────────
        table_card = Card(self)
        table_card.pack(fill="both", expand=True, padx=28, pady=(14, 28))

        # Treeview style
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Premium.Treeview",
            background=Theme.BG_CARD,
            foreground=Theme.TEXT_PRIMARY,
            fieldbackground=Theme.BG_CARD,
            rowheight=36,
            font=(Theme.FONT_MAIN, 12),
            borderwidth=0,
        )
        style.configure(
            "Premium.Treeview.Heading",
            background=Theme.BG_INPUT,
            foreground=Theme.TEXT_SECONDARY,
            font=(Theme.FONT_MAIN, 11, "bold"),
            relief="flat",
            borderwidth=0,
        )
        style.map(
            "Premium.Treeview",
            background=[("selected", "#003D5C")],
            foreground=[("selected", Theme.ACCENT_BLUE)],
        )
        style.map(
            "Premium.Treeview.Heading",
            background=[("active", Theme.BG_HOVER)]
        )

        tree_frame = ctk.CTkFrame(table_card, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=12, pady=12)

        self.tree = ttk.Treeview(
            tree_frame,
            columns=self.COLUMNS,
            show="headings",
            style="Premium.Treeview",
            selectmode="browse",
        )

        col_widths = [50, 200, 110, 100, 70, 110]
        for col, w in zip(self.COLUMNS, col_widths):
            self.tree.heading(col, text=col)
            anchor = "center" if col in ("ID", "Price (฿)", "Stock") else "w"
            self.tree.column(col, width=w, minwidth=w, anchor=anchor)

        # Scrollbar
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Tag สีแถว
        self.tree.tag_configure("alt",       background=Theme.BG_TABLE_ALT)
        self.tree.tag_configure("active",    foreground=Theme.ACCENT_GREEN)
        self.tree.tag_configure("low_stock", foreground=Theme.ACCENT_ORANGE)
        self.tree.tag_configure("out",       foreground=Theme.ACCENT_RED)

    # ── Data loading ──────────────────────────────────────────────

    def _load_data(self, *args):
        self.lbl_count.configure(text="Loading…")
        threading.Thread(target=self._fetch_thread, daemon=True).start()

    def _fetch_thread(self):
        rows = self.db.fetch_products()
        self._all_rows = rows
        self.after(0, self._render_rows, rows)

    def _render_rows(self, rows: list[tuple]):
        self.tree.delete(*self.tree.get_children())
        for i, row in enumerate(rows):
            rid, name, cat, price, stock, status = row
            display = (rid, name, cat, f"{price:,.0f}", stock, status.replace("_", " ").title())
            tag = "alt" if i % 2 == 0 else ""

            # ซ้อน tag สถานะ
            status_tag = {
                "active": "active",
                "low_stock": "low_stock",
                "out_of_stock": "out",
            }.get(status, "")
            tags = tuple(filter(None, [tag, status_tag]))
            self.tree.insert("", "end", values=display, tags=tags)

        total = len(rows)
        self.lbl_count.configure(text=f"{total} records")

    def _on_search_change(self, *args):
        keyword = self.search_var.get().lower()
        filtered = [r for r in self._all_rows if keyword in r[1].lower()]
        self._render_rows(filtered)


# ────────────────────────── SIDEBAR ──────────────────────────

class Sidebar(ctk.CTkFrame):
    """แถบเมนูซ้ายพร้อมระบบ active state"""

    MENU_ITEMS = [
        ("dashboard", "🏠   Dashboard"),
        ("sql",       "🗄   SQL Database"),
    ]

    def __init__(self, master, on_navigate, **kwargs):
        super().__init__(
            master,
            fg_color=Theme.BG_SIDEBAR,
            corner_radius=0,
            width=240,
            **kwargs
        )
        self.pack_propagate(False)
        self._on_navigate = on_navigate
        self._buttons: dict[str, ctk.CTkButton] = {}
        self._active_key = ""
        self._build()

    def _build(self):
        # ── Logo ──────────────────────────────────────────────
        logo_frame = ctk.CTkFrame(self, fg_color="transparent")
        logo_frame.pack(fill="x", padx=20, pady=(24, 0))

        logo_canvas = tk.Canvas(
            logo_frame, width=36, height=36,
            bg=Theme.BG_SIDEBAR, highlightthickness=0
        )
        logo_canvas.pack(side="left")
        logo_canvas.create_oval(2, 2, 34, 34, fill=Theme.ACCENT_BLUE, outline="")
        logo_canvas.create_text(18, 18, text="⬡", fill="#000", font=("Segoe UI", 14, "bold"))

        ctk.CTkLabel(
            logo_frame, text="PremiumApp",
            font=(Theme.FONT_MAIN, 16, "bold"),
            text_color=Theme.TEXT_PRIMARY
        ).pack(side="left", padx=(10, 0))

        # Divider
        ctk.CTkFrame(
            self, fg_color=Theme.BG_HOVER, height=1
        ).pack(fill="x", padx=16, pady=(20, 8))

        # ── Menu label ────────────────────────────────────────
        SectionLabel(self, "NAVIGATION").pack(anchor="w", padx=24, pady=(4, 8))

        # ── Menu buttons ─────────────────────────────────────
        for key, label in self.MENU_ITEMS:
            btn = ctk.CTkButton(
                self,
                text=label,
                font=(Theme.FONT_MAIN, 13),
                text_color=Theme.TEXT_SECONDARY,
                fg_color="transparent",
                hover_color=Theme.BG_HOVER,
                anchor="w",
                height=42,
                corner_radius=Theme.RADIUS_SM,
                command=lambda k=key: self._click(k),
            )
            btn.pack(fill="x", padx=12, pady=2)
            self._buttons[key] = btn

        # ── Spacer + version ─────────────────────────────────
        ctk.CTkFrame(self, fg_color="transparent").pack(expand=True, fill="y")

        ctk.CTkFrame(
            self, fg_color=Theme.BG_HOVER, height=1
        ).pack(fill="x", padx=16, pady=8)

        ctk.CTkLabel(
            self, text="v1.0.0  •  Premium Dark",
            font=(Theme.FONT_MAIN, 10),
            text_color=Theme.TEXT_DISABLED
        ).pack(pady=(0, 16))

    def _click(self, key: str):
        self.set_active(key)
        self._on_navigate(key)

    def set_active(self, key: str):
        """เปลี่ยนสีไฮไลต์ปุ่มเมนู"""
        if self._active_key and self._active_key in self._buttons:
            self._buttons[self._active_key].configure(
                fg_color="transparent",
                text_color=Theme.TEXT_SECONDARY,
            )
        self._active_key = key
        if key in self._buttons:
            self._buttons[key].configure(
                fg_color="#002640",
                text_color=Theme.ACCENT_BLUE,
            )


# ────────────────────────── MAIN WINDOW ──────────────────────────

class MainWindow(ctk.CTk):
    """หน้าต่างหลักของแอปหลังล็อกอินสำเร็จ"""

    def __init__(self, db: DatabaseManager, user: dict):
        super().__init__()
        self.db = db
        self.user = user

        ctk.set_appearance_mode("dark")
        self.title(f"PremiumApp  —  {user['username']}")
        self.geometry(self._center_geo(950, 650))
        self.minsize(800, 560)
        self.configure(fg_color=Theme.BG_MAIN)

        self._current_page: ctk.CTkFrame | None = None
        self._build_layout()
        self._navigate("dashboard")

    # ── Geometry helper ──────────────────────────────────────────

    def _center_geo(self, w: int, h: int) -> str:
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        return f"{w}x{h}+{x}+{y}"

    # ── Layout ───────────────────────────────────────────────────

    def _build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar ฝั่งซ้าย
        self.sidebar = Sidebar(self, on_navigate=self._navigate)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        # Content area ฝั่งขวา
        self.content_area = ctk.CTkFrame(self, fg_color=Theme.BG_MAIN, corner_radius=0)
        self.content_area.grid(row=0, column=1, sticky="nsew")
        self.content_area.grid_rowconfigure(0, weight=1)
        self.content_area.grid_columnconfigure(0, weight=1)

    # ── Router ───────────────────────────────────────────────────

    def _navigate(self, page_key: str):
        """ลบหน้าเก่า → สร้างหน้าใหม่ → อัปเดต sidebar"""
        if self._current_page:
            self._current_page.destroy()

        page_map = {
            "dashboard": lambda: DashboardPage(self.content_area, self.db, self.user),
            "sql":        lambda: SQLPage(self.content_area, self.db),
        }
        builder = page_map.get(page_key)
        if builder:
            self._current_page = builder()
            self._current_page.grid(row=0, column=0, sticky="nsew")

        self.sidebar.set_active(page_key)


# ────────────────────────── APP ENTRY POINT ──────────────────────────

class App:
    """จุดเริ่มต้นของโปรแกรม"""

    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.db = DatabaseManager()
        if not self.db.connect():
            messagebox.showerror(
                "Connection Error",
                "ไม่สามารถเชื่อมต่อฐานข้อมูลได้\n"
                "กรุณาตรวจสอบ DB_CONFIG หรือเปิด USE_SQLITE_FALLBACK"
            )
            return

        self._run_login()

    def _run_login(self):
        login = LoginWindow(self.db)
        login.mainloop()

        if login.result_user:
            # Login สำเร็จ → เปิดหน้าหลัก
            main = MainWindow(self.db, login.result_user)
            main.mainloop()
        else:
            # ปิดโดยไม่ล็อกอิน
            pass

        self.db.disconnect()


# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    App()
