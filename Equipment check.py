"""
Equipment Management System
Premium Dark Mode — CustomTkinter + SQL Server (pyodbc)
TE-CDBU1 · Delta Electronics (Thailand)
=======================================================
Pages:
  Login       → ตรวจสอบรหัสผ่านผ่าน SQL
  Dashboard   → สรุปสถิติ + Cal status overview
  Equipment   → CRUD + Search + QR
  Calibration → บันทึก Cal + ตาราง Due dates
  Settings    → DB config
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import io
import os
import base64
import sqlite3
from datetime import datetime, date, timedelta

# Optional imports — graceful fallback
try:
    import pyodbc
    HAS_PYODBC = True
except ImportError:
    HAS_PYODBC = False

try:
    import bcrypt
    HAS_BCRYPT = True
except ImportError:
    HAS_BCRYPT = False

try:
    import qrcode
    from PIL import Image, ImageTk
    HAS_QR = True
except ImportError:
    HAS_QR = False


# ═══════════════════════════════════════════════════════════════
#  THEME
# ═══════════════════════════════════════════════════════════════

class T:
    BG_MAIN      = "#111315"
    BG_SIDE      = "#1A1D20"
    BG_CARD      = "#212529"
    BG_INPUT     = "#2C3035"
    BG_HOVER     = "#2A2D32"
    BG_ROW_ALT   = "#1C1F23"
    BG_SEL       = "#003D5C"

    BLUE         = "#00B0FF"
    BLUE_DARK    = "#0090D6"
    BLUE_DIM     = "#002640"
    GREEN        = "#00E676"
    GREEN_DIM    = "#0D2818"
    RED          = "#FF5252"
    RED_DIM      = "#2A0A0A"
    ORANGE       = "#FF9100"
    ORANGE_DIM   = "#2A1800"
    PURPLE       = "#CE93D8"

    TEXT         = "#E8EAED"
    TEXT2        = "#9AA0A6"
    TEXT3        = "#5F6368"

    FONT         = "Segoe UI"
    R            = 10
    R_SM         = 6


# ═══════════════════════════════════════════════════════════════
#  DATABASE MANAGER
# ═══════════════════════════════════════════════════════════════

class DB:
    """
    รองรับทั้ง SQL Server (pyodbc) และ SQLite (demo mode)
    เปลี่ยน server/database ใน connect_sqlserver()
    """

    # ─── SQL Server config ─────────────────────────────────────
    SQLSERVER = dict(
        server   = r"THBPOSFPPDB\THBPOSFPPDB",   # ← แก้ server name
        database = "TE-CDBU1-Testdata",           # ← แก้ DB name
        driver   = "ODBC Driver 17 for SQL Server",
    )

    def __init__(self):
        self.conn         = None
        self.connected    = False
        self.mode         = "none"      # "sqlserver" | "sqlite"
        self._lock        = threading.Lock()

    # ── Connect ────────────────────────────────────────────────

    def connect_sqlserver(self) -> bool:
        if not HAS_PYODBC:
            return False
        try:
            cs = (
                f"DRIVER={{{self.SQLSERVER['driver']}}};"
                f"SERVER={self.SQLSERVER['server']};"
                f"DATABASE={self.SQLSERVER['database']};"
                "Trusted_Connection=yes;"
            )
            self.conn = pyodbc.connect(cs, autocommit=False, timeout=5)
            self.connected = True
            self.mode = "sqlserver"
            return True
        except Exception as e:
            print(f"[DB] SQL Server: {e}")
            return False

    def connect_sqlite(self) -> bool:
        """Demo mode — SQLite in-memory, seed ข้อมูลตัวอย่าง"""
        try:
            self.conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._seed_sqlite()
            self.connected = True
            self.mode = "sqlite"
            return True
        except Exception as e:
            print(f"[DB] SQLite: {e}")
            return False

    def connect(self) -> str:
        """ลอง SQL Server ก่อน ถ้าล้มเหลวใช้ SQLite"""
        if self.connect_sqlserver():
            return "sqlserver"
        if self.connect_sqlite():
            return "sqlite"
        return "failed"

    def close(self):
        if self.conn:
            self.conn.close()
        self.connected = False

    # ── Placeholder ─────────────────────────────────────────────
    def _ph(self):
        return "?" if self.mode == "sqlite" else "?"  # both use ?

    # ── Seed SQLite demo data ───────────────────────────────────
    def _seed_sqlite(self):
        c = self.conn.cursor()

        c.execute("""CREATE TABLE IF NOT EXISTS AppUsers (
            UserID   INTEGER PRIMARY KEY AUTOINCREMENT,
            Username TEXT NOT NULL UNIQUE,
            Password TEXT NOT NULL,
            Role     TEXT DEFAULT 'user',
            Created  TEXT DEFAULT CURRENT_TIMESTAMP
        )""")

        c.execute("""CREATE TABLE IF NOT EXISTS AssetCategories (
            CategoryID   INTEGER PRIMARY KEY AUTOINCREMENT,
            CategoryName TEXT NOT NULL UNIQUE,
            CategoryCode TEXT,
            Color        TEXT DEFAULT '#4f8ef7',
            Icon         TEXT DEFAULT '🔧',
            Description  TEXT
        )""")

        c.execute("""CREATE TABLE IF NOT EXISTS Lines (
            LineID      INTEGER PRIMARY KEY AUTOINCREMENT,
            LineName    TEXT NOT NULL UNIQUE,
            Description TEXT
        )""")

        c.execute("""CREATE TABLE IF NOT EXISTS Stations (
            StationID    INTEGER PRIMARY KEY AUTOINCREMENT,
            LineID       INTEGER REFERENCES Lines(LineID),
            StationName  TEXT NOT NULL,
            ComputerName TEXT,
            Description  TEXT,
            UpdatedAt    TEXT DEFAULT CURRENT_TIMESTAMP
        )""")

        c.execute("""CREATE TABLE IF NOT EXISTS Equipment (
            EquipmentID   INTEGER PRIMARY KEY AUTOINCREMENT,
            TagID         TEXT NOT NULL UNIQUE,
            AssetNumber   TEXT,
            CategoryID    INTEGER REFERENCES AssetCategories(CategoryID),
            EquipmentName TEXT NOT NULL,
            Brand         TEXT,
            Model         TEXT,
            SerialNumber  TEXT,
            Description   TEXT,
            IsActive      INTEGER DEFAULT 1,
            CreatedAt     TEXT DEFAULT CURRENT_TIMESTAMP
        )""")

        c.execute("""CREATE TABLE IF NOT EXISTS EquipmentAssignments (
            AssignmentID INTEGER PRIMARY KEY AUTOINCREMENT,
            EquipmentID  INTEGER REFERENCES Equipment(EquipmentID),
            StationID    INTEGER REFERENCES Stations(StationID),
            ComputerName TEXT,
            AssignedAt   TEXT DEFAULT CURRENT_TIMESTAMP,
            UnassignedAt TEXT,
            AssignedBy   TEXT,
            Remark       TEXT
        )""")

        c.execute("""CREATE TABLE IF NOT EXISTS CalibrationRecords (
            CalibrationID INTEGER PRIMARY KEY AUTOINCREMENT,
            EquipmentID   INTEGER REFERENCES Equipment(EquipmentID),
            CalDate       TEXT NOT NULL,
            CalDueDate    TEXT NOT NULL,
            CalBy         TEXT,
            CertNo        TEXT,
            Remark        TEXT,
            CreatedAt     TEXT DEFAULT CURRENT_TIMESTAMP
        )""")

        # ─ Seed users ────────────────────────────────────────
        if HAS_BCRYPT:
            pw = bcrypt.hashpw(b"admin1234", bcrypt.gensalt()).decode()
        else:
            pw = "admin1234"  # plain fallback
        c.execute("INSERT OR IGNORE INTO AppUsers (Username,Password,Role) VALUES (?,?,?)",
                  ("admin", pw, "admin"))

        # ─ Seed categories ───────────────────────────────────
        cats = [
            ("Digital Multimeter", "DMM", "#4f8ef7", "🔌"),
            ("Oscilloscope",       "OSC", "#a855f7", "📡"),
            ("Power Supply",       "PWR", "#f59e0b", "⚡"),
            ("LCR Meter",          "LCR", "#22c55e", "🔬"),
            ("ATE / ATS",          "ATE", "#ef4444", "🤖"),
            ("Safety Tester",      "SAF", "#f97316", "⚠️"),
            ("Other",              "OTH", "#64748b", "📦"),
        ]
        c.executemany(
            "INSERT OR IGNORE INTO AssetCategories (CategoryName,CategoryCode,Color,Icon) VALUES (?,?,?,?)",
            cats
        )

        # ─ Seed lines & stations ─────────────────────────────
        c.execute("INSERT OR IGNORE INTO Lines (LineName) VALUES (?)", ("LINE-A",))
        c.execute("INSERT OR IGNORE INTO Lines (LineName) VALUES (?)", ("LINE-B",))
        c.execute("INSERT OR IGNORE INTO Stations (LineID,StationName,ComputerName) VALUES (1,'ST-01','DESKTOP-PC01')")
        c.execute("INSERT OR IGNORE INTO Stations (LineID,StationName,ComputerName) VALUES (1,'ST-02','DESKTOP-PC02')")
        c.execute("INSERT OR IGNORE INTO Stations (LineID,StationName,ComputerName) VALUES (2,'ST-01','DESKTOP-PC03')")

        # ─ Seed equipment ────────────────────────────────────
        equip = [
            ("EQ-001", "AST-001", 1, "Fluke 87V",     "Fluke",  "87V",  "SN-F001"),
            ("EQ-002", "AST-002", 2, "Rigol DS1054Z",  "Rigol",  "DS1054Z", "SN-R002"),
            ("EQ-003", "AST-003", 3, "Keysight E36313A","Keysight","E36313A","SN-K003"),
            ("EQ-004", "AST-004", 1, "Fluke 115",      "Fluke",  "115",  "SN-F004"),
            ("EQ-005", "AST-005", 5, "Chroma 8000",    "Chroma", "8000", "SN-C005"),
        ]
        c.executemany("""INSERT OR IGNORE INTO Equipment
            (TagID,AssetNumber,CategoryID,EquipmentName,Brand,Model,SerialNumber)
            VALUES (?,?,?,?,?,?,?)""", equip)

        # ─ Seed assignments ──────────────────────────────────
        assigns = [
            (1, 1, "DESKTOP-PC01"), (2, 2, "DESKTOP-PC02"),
            (3, 3, "DESKTOP-PC03"), (4, 1, "DESKTOP-PC01"),
            (5, 2, "DESKTOP-PC02"),
        ]
        c.executemany("""INSERT OR IGNORE INTO EquipmentAssignments
            (EquipmentID,StationID,ComputerName) VALUES (?,?,?)""", assigns)

        # ─ Seed calibrations (บางตัว overdue) ────────────────
        today = date.today()
        cals = [
            (1, "2024-12-01", (today + timedelta(days=45)).isoformat(), "Delta Cal Lab", "CERT-001"),
            (2, "2024-11-15", (today + timedelta(days=10)).isoformat(), "External Lab",  "CERT-002"),
            (3, "2024-10-01", (today - timedelta(days=20)).isoformat(), "In-house",      "CERT-003"),
            (4, "2024-08-01", (today - timedelta(days=60)).isoformat(), "Delta Cal Lab", "CERT-004"),
        ]
        c.executemany("""INSERT OR IGNORE INTO CalibrationRecords
            (EquipmentID,CalDate,CalDueDate,CalBy,CertNo) VALUES (?,?,?,?,?)""", cals)

        self.conn.commit()

    # ── Auth ───────────────────────────────────────────────────

    def verify_login(self, username: str, password: str):
        # ── DEV MODE: ข้ามตรวจสอบ password ─────────────────
        # ลบบรรทัดนี้ออกเมื่อ deploy จริง
        if username.strip():
            return {"id": 0, "username": username.strip(), "role": "admin"}
        # ────────────────────────────────────────────────────
        try:
            c = self.conn.cursor()
            c.execute(
                "SELECT UserID,Username,Password,Role FROM AppUsers WHERE Username=?",
                (username,)
            )
            row = c.fetchone()
            if not row:
                return None
            uid, uname, hashed, role = row
            if HAS_BCRYPT:
                ok = bcrypt.checkpw(password.encode(), hashed.encode())
            else:
                ok = (password == hashed)
            return {"id": uid, "username": uname, "role": role} if ok else None
        except Exception as e:
            print(f"[DB] login: {e}")
            return None

    # ── Equipment queries ──────────────────────────────────────

    def fetch_equipment_status(self, search="", cat_id=None, cal_status=None):
        try:
            c = self.conn.cursor()
            if self.mode == "sqlite":
                sql = """
                SELECT
                    e.EquipmentID, e.TagID, e.AssetNumber,
                    ac.CategoryName, ac.Icon, ac.Color,
                    e.EquipmentName, e.Brand, e.Model, e.SerialNumber,
                    l.LineName, s.StationName, ea.ComputerName,
                    cr.CalDate, cr.CalDueDate, cr.CertNo,
                    CAST(julianday(cr.CalDueDate) - julianday('now') AS INTEGER) AS DaysLeft
                FROM Equipment e
                LEFT JOIN AssetCategories ac ON e.CategoryID = ac.CategoryID
                LEFT JOIN EquipmentAssignments ea ON e.EquipmentID = ea.EquipmentID
                    AND ea.UnassignedAt IS NULL
                LEFT JOIN Stations s ON ea.StationID = s.StationID
                LEFT JOIN Lines l ON s.LineID = l.LineID
                LEFT JOIN (
                    SELECT cr1.* FROM CalibrationRecords cr1
                    INNER JOIN (
                        SELECT EquipmentID, MAX(CalDate) AS mx
                        FROM CalibrationRecords GROUP BY EquipmentID
                    ) cr2 ON cr1.EquipmentID=cr2.EquipmentID AND cr1.CalDate=cr2.mx
                ) cr ON e.EquipmentID = cr.EquipmentID
                WHERE e.IsActive=1
                """
                params = []
                if search:
                    sql += " AND (e.TagID LIKE ? OR e.EquipmentName LIKE ? OR e.AssetNumber LIKE ?)"
                    params += [f"%{search}%"] * 3
                if cat_id:
                    sql += " AND e.CategoryID=?"
                    params.append(cat_id)
                sql += " ORDER BY DaysLeft ASC"
                c.execute(sql, params)
            else:
                # SQL Server version
                sql = """
                SELECT
                    e.EquipmentID, e.TagID, e.AssetNumber,
                    ac.CategoryName, ac.Icon, ac.Color,
                    e.EquipmentName, e.Brand, e.Model, e.SerialNumber,
                    l.LineName, s.StationName, ea.ComputerName,
                    cr.CalDate, cr.CalDueDate, cr.CertNo,
                    DATEDIFF(DAY, GETDATE(), cr.CalDueDate) AS DaysLeft
                FROM Equipment e
                LEFT JOIN AssetCategories ac ON e.CategoryID = ac.CategoryID
                LEFT JOIN EquipmentAssignments ea ON e.EquipmentID = ea.EquipmentID
                    AND ea.UnassignedAt IS NULL
                LEFT JOIN Stations s ON ea.StationID = s.StationID
                LEFT JOIN Lines l ON s.LineID = l.LineID
                LEFT JOIN (
                    SELECT cr1.* FROM CalibrationRecords cr1
                    INNER JOIN (
                        SELECT EquipmentID, MAX(CalDate) AS mx
                        FROM CalibrationRecords GROUP BY EquipmentID
                    ) cr2 ON cr1.EquipmentID=cr2.EquipmentID AND cr1.CalDate=cr2.mx
                ) cr ON e.EquipmentID = cr.EquipmentID
                WHERE e.IsActive=1
                """
                params = []
                if search:
                    sql += " AND (e.TagID LIKE ? OR e.EquipmentName LIKE ? OR e.AssetNumber LIKE ?)"
                    params += [f"%{search}%"] * 3
                if cat_id:
                    sql += " AND e.CategoryID=?"
                    params.append(cat_id)
                sql += " ORDER BY DaysLeft ASC"
                c.execute(sql, params)
            return c.fetchall()
        except Exception as e:
            print(f"[DB] fetch_equipment: {e}")
            return []

    def get_dashboard_stats(self):
        try:
            c = self.conn.cursor()
            if self.mode == "sqlite":
                today = date.today().isoformat()
                due30 = (date.today() + timedelta(days=30)).isoformat()

                c.execute("SELECT COUNT(*) FROM Equipment WHERE IsActive=1")
                total = c.fetchone()[0]

                # get latest cal per equipment
                c.execute("""
                    SELECT e.EquipmentID,
                        (SELECT CalDueDate FROM CalibrationRecords
                         WHERE EquipmentID=e.EquipmentID ORDER BY CalDate DESC LIMIT 1) AS due
                    FROM Equipment e WHERE IsActive=1
                """)
                rows = c.fetchall()
                ok = due_soon = overdue = no_cal = 0
                for _, due in rows:
                    if due is None:
                        no_cal += 1
                    elif due < today:
                        overdue += 1
                    elif due <= due30:
                        due_soon += 1
                    else:
                        ok += 1
            else:
                today = date.today()
                c.execute("SELECT COUNT(*) FROM Equipment WHERE IsActive=1")
                total = c.fetchone()[0]
                c.execute("""
                    SELECT
                        SUM(CASE WHEN CalStatus='OK'       THEN 1 ELSE 0 END),
                        SUM(CASE WHEN CalStatus='DUE_SOON' THEN 1 ELSE 0 END),
                        SUM(CASE WHEN CalStatus='OVERDUE'  THEN 1 ELSE 0 END),
                        SUM(CASE WHEN CalStatus='NO_CAL'   THEN 1 ELSE 0 END)
                    FROM vw_EquipmentStatus
                """)
                r = c.fetchone()
                ok, due_soon, overdue, no_cal = (r[0] or 0, r[1] or 0, r[2] or 0, r[3] or 0)
            return dict(total=total, ok=ok, due_soon=due_soon, overdue=overdue, no_cal=no_cal)
        except Exception as e:
            print(f"[DB] stats: {e}")
            return dict(total=0, ok=0, due_soon=0, overdue=0, no_cal=0)

    def fetch_categories(self):
        try:
            c = self.conn.cursor()
            c.execute("SELECT CategoryID, CategoryName, CategoryCode, Icon, Color FROM AssetCategories ORDER BY CategoryName")
            return c.fetchall()
        except:
            return []

    def add_equipment(self, tag, asset, cat_id, name, brand, model, serial, desc) -> bool:
        try:
            c = self.conn.cursor()
            c.execute("""INSERT INTO Equipment
                (TagID,AssetNumber,CategoryID,EquipmentName,Brand,Model,SerialNumber,Description)
                VALUES (?,?,?,?,?,?,?,?)""",
                (tag, asset or None, cat_id or None, name,
                 brand or None, model or None, serial or None, desc or None))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"[DB] add_equip: {e}")
            return False

    def add_calibration(self, eq_id, cal_date, due_date, cal_by, cert_no, remark) -> bool:
        try:
            c = self.conn.cursor()
            c.execute("""INSERT INTO CalibrationRecords
                (EquipmentID,CalDate,CalDueDate,CalBy,CertNo,Remark) VALUES (?,?,?,?,?,?)""",
                (eq_id, cal_date, due_date, cal_by or None, cert_no or None, remark or None))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"[DB] add_cal: {e}")
            return False

    def get_assignment_history(self, eq_id):
        try:
            c = self.conn.cursor()
            c.execute("""
                SELECT ea.AssignedAt, ea.UnassignedAt, l.LineName, s.StationName,
                       ea.ComputerName, ea.AssignedBy, ea.Remark
                FROM EquipmentAssignments ea
                LEFT JOIN Stations s ON ea.StationID = s.StationID
                LEFT JOIN Lines l ON s.LineID = l.LineID
                WHERE ea.EquipmentID=? ORDER BY ea.AssignedAt DESC
            """, (eq_id,))
            return c.fetchall()
        except:
            return []


# ═══════════════════════════════════════════════════════════════
#  SHARED WIDGETS
# ═══════════════════════════════════════════════════════════════

def card(master, **kw):
    return ctk.CTkFrame(master, fg_color=T.BG_CARD, corner_radius=T.R, **kw)

def label(master, text, size=13, bold=False, color=None, **kw):
    return ctk.CTkLabel(master, text=text,
                        font=(T.FONT, size, "bold" if bold else "normal"),
                        text_color=color or T.TEXT, **kw)

def small_label(master, text, **kw):
    return ctk.CTkLabel(master, text=text,
                        font=(T.FONT, 10, "bold"),
                        text_color=T.TEXT2, **kw)

def primary_btn(master, text, cmd, width=None, **kw):
    return ctk.CTkButton(master, text=text, command=cmd,
                         fg_color=T.BLUE, hover_color=T.BLUE_DARK,
                         text_color="#000", font=(T.FONT, 13, "bold"),
                         corner_radius=T.R_SM, height=38,
                         width=width or 120, **kw)

def ghost_btn(master, text, cmd, width=None, **kw):
    return ctk.CTkButton(master, text=text, command=cmd,
                         fg_color=T.BG_HOVER, hover_color=T.BG_INPUT,
                         text_color=T.TEXT2, font=(T.FONT, 12),
                         corner_radius=T.R_SM, height=34,
                         width=width or 100, **kw)

def entry(master, placeholder="", width=None, show=None, **kw):
    e = ctk.CTkEntry(master, placeholder_text=placeholder,
                     fg_color=T.BG_INPUT, border_color=T.BG_HOVER,
                     text_color=T.TEXT, font=(T.FONT, 13),
                     corner_radius=T.R_SM, height=38,
                     width=width or 200, **kw)
    if show:
        e.configure(show=show)
    return e

def combo(master, values, width=None, **kw):
    return ctk.CTkComboBox(master, values=values,
                           fg_color=T.BG_INPUT, border_color=T.BG_HOVER,
                           button_color=T.BG_HOVER, button_hover_color=T.BLUE,
                           text_color=T.TEXT, font=(T.FONT, 13),
                           dropdown_fg_color=T.BG_CARD,
                           dropdown_text_color=T.TEXT,
                           corner_radius=T.R_SM, height=38,
                           width=width or 200, **kw)

def stat_card(master, value, label_text, color, col):
    """Card ตัวเลขสถิติ"""
    f = card(master)
    f.grid(row=0, column=col, padx=(0, 10), sticky="ew")
    ctk.CTkLabel(f, text=str(value),
                 font=(T.FONT, 36, "bold"), text_color=color).pack(pady=(16, 0))
    ctk.CTkLabel(f, text=label_text,
                 font=(T.FONT, 11), text_color=T.TEXT2).pack(pady=(2, 14))

def cal_status(days) -> tuple[str, str, str]:
    """(text, fg_color, bg_color)"""
    if days is None:
        return "No Cal", T.TEXT3, T.BG_HOVER
    if days < 0:
        return f"Overdue {abs(days)}d", T.RED, T.RED_DIM
    if days <= 30:
        return f"Due {days}d", T.ORANGE, T.ORANGE_DIM
    return f"OK {days}d", T.GREEN, T.GREEN_DIM


def build_treeview(parent, columns: list[tuple], height=18):
    """สร้าง ttk.Treeview สไตล์ premium dark"""
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("EQ.Treeview",
                    background=T.BG_CARD, foreground=T.TEXT,
                    fieldbackground=T.BG_CARD, rowheight=34,
                    font=(T.FONT, 12), borderwidth=0, relief="flat")
    style.configure("EQ.Treeview.Heading",
                    background=T.BG_INPUT, foreground=T.TEXT2,
                    font=(T.FONT, 11, "bold"), relief="flat")
    style.map("EQ.Treeview",
              background=[("selected", T.BG_SEL)],
              foreground=[("selected", T.BLUE)])
    style.map("EQ.Treeview.Heading",
              background=[("active", T.BG_HOVER)])

    frame = ctk.CTkFrame(parent, fg_color="transparent")
    frame.pack(fill="both", expand=True, padx=12, pady=12)

    col_ids = [c[0] for c in columns]
    tree = ttk.Treeview(frame, columns=col_ids, show="headings",
                        style="EQ.Treeview", height=height)

    for col_id, col_name, col_w, anchor in columns:
        tree.heading(col_id, text=col_name)
        tree.column(col_id, width=col_w, minwidth=col_w, anchor=anchor)

    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")

    tree.tag_configure("alt",      background=T.BG_ROW_ALT)
    tree.tag_configure("overdue",  foreground=T.RED)
    tree.tag_configure("due_soon", foreground=T.ORANGE)
    tree.tag_configure("ok",       foreground=T.GREEN)
    tree.tag_configure("no_cal",   foreground=T.TEXT3)

    return tree


# ═══════════════════════════════════════════════════════════════
#  LOGIN WINDOW
# ═══════════════════════════════════════════════════════════════

class LoginWin(ctk.CTk):
    def __init__(self, db: DB):
        super().__init__()
        self.db = db
        self.logged_user = None
        ctk.set_appearance_mode("dark")
        self.title("Equipment Management — Login")
        self.resizable(False, False)
        w, h = 480, 560
        self.geometry(self._center(w, h))
        self.configure(fg_color=T.BG_MAIN)
        self._build()

    def _center(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        return f"{w}x{h}+{x}+{y}"

    def _build(self):
        # ─ Logo ────────────────────────────────────────────
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(pady=(48, 0))

        cvs = tk.Canvas(top, width=64, height=64,
                        bg=T.BG_MAIN, highlightthickness=0)
        cvs.pack()
        cvs.create_oval(3, 3, 61, 61, fill=T.BG_CARD, outline=T.BLUE, width=2)
        cvs.create_text(32, 32, text="⚙", fill=T.BLUE, font=(T.FONT, 22, "bold"))

        label(self, "Equipment Management", 18, True).pack(pady=(10, 2))
        label(self, "TE-CDBU1 · Delta Electronics (Thailand)", 11,
              color=T.TEXT2).pack()

        # ─ Card ────────────────────────────────────────────
        f = card(self)
        f.pack(pady=24, padx=44, fill="x")
        inner = ctk.CTkFrame(f, fg_color="transparent")
        inner.pack(padx=28, pady=28, fill="x")

        small_label(inner, "USERNAME").pack(anchor="w", pady=(0, 4))
        self._eu = entry(inner, "กรอก username", width=340)
        self._eu.pack(fill="x")

        small_label(inner, "PASSWORD").pack(anchor="w", pady=(14, 4))
        self._ep = entry(inner, "กรอก password", width=340, show="●")
        self._ep.pack(fill="x")
        self._ep.bind("<Return>", lambda e: self._login())
        self._eu.bind("<Return>", lambda e: self._ep.focus())

        self._err = ctk.CTkLabel(self, text="",
                                 text_color=T.RED, font=(T.FONT, 12))
        self._err.pack()

        self._btn = primary_btn(self, "Sign In", self._login, width=340)
        self._btn.pack()

        # ─ Mode label ──────────────────────────────────────
        mode_color = T.GREEN if self.db.mode == "sqlite" else T.BLUE
        mode_text  = "● SQLite Demo Mode" if self.db.mode == "sqlite" else f"● SQL Server: {self.db.SQLSERVER['server']}"
        label(self, mode_text, 10, color=mode_color).pack(pady=(14, 0))
        label(self, "🔓 DEV MODE — กรอก username อะไรก็ได้ กด Sign In", 10, color=T.ORANGE).pack(pady=2)

    def _login(self):
        u, p = self._eu.get().strip(), self._ep.get()
        if not u or not p:
            self._err.configure(text="⚠  กรุณากรอก username และ password")
            return
        self._btn.configure(state="disabled", text="กำลังตรวจสอบ…")
        self.update()
        user = self.db.verify_login(u, p)
        if user:
            self.logged_user = user
            self.destroy()
        else:
            self._btn.configure(state="normal", text="Sign In")
            self._err.configure(text="✗  Username หรือ Password ไม่ถูกต้อง")


# ═══════════════════════════════════════════════════════════════
#  SIDEBAR
# ═══════════════════════════════════════════════════════════════

MENU = [
    ("dashboard",   "🏠   Dashboard"),
    ("equipment",   "🔧   Equipment"),
    ("calibration", "📅   Calibration"),
    ("settings",    "⚙    Settings"),
]

class Sidebar(ctk.CTkFrame):
    def __init__(self, master, on_nav, user: dict):
        super().__init__(master, fg_color=T.BG_SIDE,
                         corner_radius=0, width=240)
        self.pack_propagate(False)
        self._on_nav = on_nav
        self._btns   = {}
        self._active = ""
        self._build(user)

    def _build(self, user):
        # ─ Logo ────────────────────────────────────────────
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=(22, 0))

        cvs = tk.Canvas(top, width=34, height=34,
                        bg=T.BG_SIDE, highlightthickness=0)
        cvs.pack(side="left")
        cvs.create_oval(2, 2, 32, 32, fill=T.BLUE, outline="")
        cvs.create_text(17, 17, text="⚙", fill="#000", font=(T.FONT, 13, "bold"))

        ctk.CTkLabel(top, text="Equip Mgmt",
                     font=(T.FONT, 14, "bold"),
                     text_color=T.TEXT).pack(side="left", padx=(10, 0))

        # Divider
        ctk.CTkFrame(self, fg_color=T.BG_HOVER, height=1).pack(
            fill="x", padx=14, pady=(18, 6))

        # ─ Section label ───────────────────────────────────
        ctk.CTkLabel(self, text="NAVIGATION",
                     font=(T.FONT, 10, "bold"),
                     text_color=T.TEXT3).pack(anchor="w", padx=22, pady=(2, 6))

        # ─ Menu buttons ────────────────────────────────────
        for key, lbl in MENU:
            btn = ctk.CTkButton(
                self, text=lbl,
                font=(T.FONT, 13), text_color=T.TEXT2,
                fg_color="transparent", hover_color=T.BG_HOVER,
                anchor="w", height=42, corner_radius=T.R_SM,
                command=lambda k=key: self._click(k)
            )
            btn.pack(fill="x", padx=10, pady=2)
            self._btns[key] = btn

        # ─ Spacer ──────────────────────────────────────────
        ctk.CTkFrame(self, fg_color="transparent").pack(expand=True, fill="y")
        ctk.CTkFrame(self, fg_color=T.BG_HOVER, height=1).pack(
            fill="x", padx=14, pady=6)

        # ─ User info ───────────────────────────────────────
        ctk.CTkLabel(self,
                     text=f"👤  {user['username']}  [{user['role']}]",
                     font=(T.FONT, 11), text_color=T.TEXT2).pack(pady=(2, 4))
        ctk.CTkLabel(self, text="v2.0  •  TE-CDBU1",
                     font=(T.FONT, 10), text_color=T.TEXT3).pack(pady=(0, 14))

    def _click(self, key):
        self.set_active(key)
        self._on_nav(key)

    def set_active(self, key):
        if self._active and self._active in self._btns:
            self._btns[self._active].configure(
                fg_color="transparent", text_color=T.TEXT2)
        self._active = key
        if key in self._btns:
            self._btns[key].configure(
                fg_color=T.BLUE_DIM, text_color=T.BLUE)


# ═══════════════════════════════════════════════════════════════
#  PAGE: DASHBOARD
# ═══════════════════════════════════════════════════════════════

class DashboardPage(ctk.CTkFrame):
    def __init__(self, master, db: DB, user: dict):
        super().__init__(master, fg_color=T.BG_MAIN)
        self.db = db
        self.user = user
        self._build()
        self._load()

    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=26, pady=(26, 0))
        label(hdr, "Dashboard", 22, True).pack(side="left")
        label(hdr, datetime.now().strftime("%d %b %Y  %H:%M"),
              12, color=T.TEXT2).pack(side="right", pady=4)

        # DB Connection card
        c = card(self)
        c.pack(fill="x", padx=26, pady=(14, 0))
        row = ctk.CTkFrame(c, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=12)
        label(row, "Database Connection", 13, True).pack(side="left")
        dot  = T.GREEN if self.db.connected else T.RED
        txt  = "● Connected" if self.db.connected else "● Disconnected"
        mode = f"[{self.db.mode.upper()}]"
        label(row, txt, 12, color=dot).pack(side="right", padx=(0, 8))
        label(row, mode, 11, color=T.TEXT3).pack(side="right", padx=(0, 4))

        if self.db.mode == "sqlserver":
            srv = self.db.SQLSERVER['server']
            label(row, f"Server: {srv}", 10, color=T.TEXT3).pack(
                side="right", padx=(0, 10))

        # Stats grid
        self._stat_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._stat_frame.pack(fill="x", padx=26, pady=(14, 0))
        self._stat_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1, uniform="s")

        # Due-soon list card
        label(self, "🗓   Upcoming Calibrations", 13, True,
              color=T.TEXT2).pack(anchor="w", padx=26, pady=(18, 6))
        self._due_card = card(self)
        self._due_card.pack(fill="both", expand=True, padx=26, pady=(0, 26))

    def _load(self):
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self):
        stats = self.db.get_dashboard_stats()
        rows  = self.db.fetch_equipment_status()
        self.after(0, self._render, stats, rows)

    def _render(self, s, rows):
        # Clear & rebuild stat cards
        for w in self._stat_frame.winfo_children():
            w.destroy()
        stat_card(self._stat_frame, s['total'],    "📦  Total",      T.BLUE,   0)
        stat_card(self._stat_frame, s['ok'],        "✅  OK",          T.GREEN,  1)
        stat_card(self._stat_frame, s['due_soon'],  "⏳  Due Soon",    T.ORANGE, 2)
        stat_card(self._stat_frame, s['overdue'],   "🚨  Overdue",     T.RED,    3)
        stat_card(self._stat_frame, s['no_cal'],    "❓  No Cal",      T.TEXT3,  4)

        # Due list
        for w in self._due_card.winfo_children():
            w.destroy()

        urgent = [r for r in rows
                  if r[16] is not None and r[16] <= 30][:8]
        if not urgent:
            label(self._due_card, "✅  ไม่มี Equipment ที่ใกล้หมดอายุ Cal",
                  12, color=T.TEXT2).pack(pady=24)
            return

        hdr = ctk.CTkFrame(self._due_card, fg_color=T.BG_INPUT)
        hdr.pack(fill="x", padx=12, pady=(10, 0))
        for txt, w in [("Tag ID", 100), ("Equipment", 200),
                       ("Line / Station", 160), ("Due Date", 110), ("Days", 80)]:
            ctk.CTkLabel(hdr, text=txt, font=(T.FONT, 10, "bold"),
                         text_color=T.TEXT2, width=w, anchor="w").pack(
                side="left", padx=8, pady=6)

        for i, r in enumerate(urgent):
            days = r[16]
            txt, clr, _ = cal_status(days)
            row_bg = T.BG_ROW_ALT if i % 2 == 0 else "transparent"
            row_f = ctk.CTkFrame(self._due_card, fg_color=row_bg)
            row_f.pack(fill="x", padx=12)

            station_txt = f"{r[10] or '—'} / {r[11] or '—'}"
            for val, w in [(r[1], 100), (r[6], 200),
                           (station_txt, 160), (str(r[14] or '—'), 110)]:
                ctk.CTkLabel(row_f, text=str(val), font=(T.FONT, 12),
                             text_color=T.TEXT, width=w, anchor="w").pack(
                    side="left", padx=8, pady=5)
            ctk.CTkLabel(row_f, text=txt, font=(T.FONT, 11, "bold"),
                         text_color=clr, width=80, anchor="w").pack(
                side="left", padx=8)


# ═══════════════════════════════════════════════════════════════
#  PAGE: EQUIPMENT
# ═══════════════════════════════════════════════════════════════

EQ_COLS = [
    ("TagID",    "Tag ID",      90,  "w"),
    ("Cat",      "Category",    110, "w"),
    ("Name",     "Equipment",   180, "w"),
    ("Brand",    "Brand/Model", 140, "w"),
    ("Serial",   "Serial No.",  110, "w"),
    ("Line",     "Line",        80,  "w"),
    ("Station",  "Station",     80,  "w"),
    ("Computer", "Computer",    130, "w"),
    ("Due",      "Cal Due",     90,  "center"),
    ("Status",   "Status",      100, "center"),
]

class EquipmentPage(ctk.CTkFrame):
    def __init__(self, master, db: DB):
        super().__init__(master, fg_color=T.BG_MAIN)
        self.db = db
        self._all_rows = []
        self._cats = []
        self._build()
        self._load()

    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=26, pady=(26, 0))
        label(hdr, "Equipment / Assets", 22, True).pack(side="left")
        primary_btn(hdr, "＋  เพิ่ม Equipment", self._open_add).pack(side="right")

        # Toolbar
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=26, pady=(12, 0))

        self._sv = tk.StringVar()
        self._sv.trace_add("write", lambda *_: self._filter())
        se = entry(bar, "🔍  ค้นหา Tag / ชื่อ / Asset No.", width=280)
        se.configure(textvariable=self._sv)
        se.pack(side="left")

        self._cat_var = tk.StringVar(value="All Categories")
        self._cat_combo = combo(bar, ["All Categories"], width=180)
        self._cat_combo.pack(side="left", padx=(10, 0))
        self._cat_combo.configure(command=lambda _: self._filter())

        ghost_btn(bar, "🔄 Refresh", self._load).pack(side="left", padx=(10, 0))

        self._count_lbl = label(bar, "", 11, color=T.TEXT2)
        self._count_lbl.pack(side="right")

        # Table card
        tc = card(self)
        tc.pack(fill="both", expand=True, padx=26, pady=(12, 26))
        self._tree = build_treeview(tc, EQ_COLS)
        self._tree.bind("<Double-1>", self._on_dbl_click)

    def _load(self):
        self._cats = self.db.fetch_categories()
        cat_names = ["All Categories"] + [f"{c[3]} {c[1]}" for c in self._cats]
        self._cat_combo.configure(values=cat_names)
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self):
        rows = self.db.fetch_equipment_status()
        self._all_rows = rows
        self.after(0, self._render, rows)

    def _filter(self):
        kw   = self._sv.get().lower()
        sel  = self._cat_combo.get()
        cat_id = None
        if sel != "All Categories":
            for c in self._cats:
                if f"{c[3]} {c[1]}" == sel:
                    cat_id = c[0]; break

        filtered = []
        for r in self._all_rows:
            if kw and kw not in (r[1] or "").lower() \
                   and kw not in (r[6] or "").lower() \
                   and kw not in (r[2] or "").lower():
                continue
            if cat_id and r[3] != self._cats[[c[0] for c in self._cats].index(cat_id)][1]:
                continue
            filtered.append(r)
        self._render(filtered)

    def _render(self, rows):
        self._tree.delete(*self._tree.get_children())
        for i, r in enumerate(rows):
            days = r[16]
            status_txt, *_ = cal_status(days)
            cat_txt = f"{r[4] or ''} {r[3] or ''}".strip() if r[3] else "—"
            values = (
                r[1],                                   # TagID
                cat_txt,                                # Category
                r[6],                                   # Name
                f"{r[7] or ''} {r[8] or ''}".strip() or "—",  # Brand/Model
                r[9] or "—",                            # Serial
                r[10] or "—",                           # Line
                r[11] or "—",                           # Station
                r[12] or "—",                           # Computer
                str(r[14]) if r[14] else "—",           # Due
                status_txt,                             # Status
            )
            tags = []
            if i % 2 == 0: tags.append("alt")
            if days is None:            tags.append("no_cal")
            elif days < 0:              tags.append("overdue")
            elif days <= 30:            tags.append("due_soon")
            else:                       tags.append("ok")
            self._tree.insert("", "end", values=values, tags=tags, iid=str(r[0]))

        self._count_lbl.configure(text=f"{len(rows)} รายการ")

    def _on_dbl_click(self, event):
        iid = self._tree.focus()
        if not iid:
            return
        eq_id = int(iid)
        row = next((r for r in self._all_rows if r[0] == eq_id), None)
        if row:
            DetailDialog(self, self.db, row)

    def _open_add(self):
        AddEquipDialog(self, self.db, on_save=self._load)


# ── Equipment Detail Dialog ────────────────────────────────────

class DetailDialog(ctk.CTkToplevel):
    def __init__(self, master, db: DB, row):
        super().__init__(master)
        self.db = db
        self.row = row
        self.title(f"Equipment — {row[1]}")
        w, h = 620, 520
        self.geometry(self._center(w, h))
        self.configure(fg_color=T.BG_MAIN)
        self.grab_set()
        self._build()

    def _center(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        return f"{w}x{h}+{x}+{y}"

    def _build(self):
        r = self.row
        label(self, f"{r[1]}  —  {r[6]}", 18, True).pack(pady=(20, 0), padx=24, anchor="w")
        cat_txt = f"{r[4] or ''} {r[3] or ''}".strip() or "—"
        label(self, cat_txt, 12, color=T.TEXT2).pack(padx=24, anchor="w")

        nb = ctk.CTkTabview(self, fg_color=T.BG_CARD,
                            segmented_button_fg_color=T.BG_CARD,
                            segmented_button_selected_color=T.BLUE_DIM,
                            segmented_button_selected_hover_color=T.BLUE_DIM,
                            segmented_button_unselected_color=T.BG_CARD,
                            text_color=T.TEXT)
        nb.pack(fill="both", expand=True, padx=20, pady=(12, 12))
        nb.add("📋  Info")
        nb.add("📍  Assignment")
        nb.add("🖨  QR Code")

        # ─ Info tab ──────────────────────────────────────
        info_tab = nb.tab("📋  Info")
        rows_info = [
            ("Tag ID",       r[1]),
            ("Asset No.",    r[2] or "—"),
            ("Brand",        r[7] or "—"),
            ("Model",        r[8] or "—"),
            ("Serial No.",   r[9] or "—"),
            ("Line",         r[10] or "—"),
            ("Station",      r[11] or "—"),
            ("Computer",     r[12] or "—"),
            ("Last Cal",     str(r[13]) if r[13] else "—"),
            ("Cal Due",      str(r[14]) if r[14] else "—"),
            ("Cert No.",     r[15] or "—"),
        ]
        for key, val in rows_info:
            rw = ctk.CTkFrame(info_tab, fg_color="transparent")
            rw.pack(fill="x", padx=6, pady=2)
            label(rw, key, 11, color=T.TEXT2, width=110).pack(side="left")
            label(rw, val, 12).pack(side="left", padx=8)

        # ─ Assignment history tab ─────────────────────────
        hist_tab = nb.tab("📍  Assignment")
        hist = self.db.get_assignment_history(r[0])
        if not hist:
            label(hist_tab, "ยังไม่มี history", 12, color=T.TEXT2).pack(pady=24)
        for h in hist[:10]:
            hw = ctk.CTkFrame(hist_tab, fg_color=T.BG_INPUT,
                              corner_radius=T.R_SM)
            hw.pack(fill="x", padx=6, pady=3)
            top_row = ctk.CTkFrame(hw, fg_color="transparent")
            top_row.pack(fill="x", padx=10, pady=(8, 2))
            line_st = f"{h[2] or '—'} › {h[3] or '—'}"
            label(top_row, line_st, 12, True).pack(side="left")
            label(top_row, f"💻  {h[4] or '—'}", 11, color=T.BLUE).pack(side="right")
            bot_row = ctk.CTkFrame(hw, fg_color="transparent")
            bot_row.pack(fill="x", padx=10, pady=(0, 6))
            in_date = (str(h[0]) or "")[:16]
            out_date = (str(h[1]) or "")[:16] if h[1] else "ยังอยู่ที่นี่"
            out_color = T.TEXT2 if h[1] else T.GREEN
            label(bot_row, f"เข้า: {in_date}", 10, color=T.TEXT2).pack(side="left")
            label(bot_row, f"ออก: {out_date}", 10, color=out_color).pack(side="left", padx=12)
            if h[6]:
                label(bot_row, h[6], 10, color=T.TEXT3).pack(side="right")

        # ─ QR tab ────────────────────────────────────────
        qr_tab = nb.tab("🖨  QR Code")
        if HAS_QR:
            qr_data = f"Equipment:{r[1]}|{r[6]}|SN:{r[9] or '—'}"
            qr_img = qrcode.make(qr_data)
            qr_img = qr_img.resize((180, 180))
            self._qr_img = ImageTk.PhotoImage(qr_img)
            ctk.CTkLabel(qr_tab, image=self._qr_img, text="").pack(pady=(16, 8))
            label(qr_tab, f"Tag ID: {r[1]}", 13, True).pack()
            label(qr_tab, f"{r[6]}", 11, color=T.TEXT2).pack()
            label(qr_tab, f"S/N: {r[9] or '—'}", 11, color=T.TEXT3).pack(pady=2)
            primary_btn(qr_tab, "💾  Save QR Image", self._save_qr).pack(pady=12)
        else:
            label(qr_tab, "ติดตั้ง qrcode และ pillow เพื่อใช้ฟีเจอร์นี้\npip install qrcode[pil] pillow",
                  12, color=T.TEXT2).pack(pady=40)

    def _save_qr(self):
        if not HAS_QR:
            return
        r = self.row
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            initialfile=f"QR_{r[1]}.png",
            filetypes=[("PNG", "*.png")]
        )
        if path:
            qr_data = f"Equipment:{r[1]}|{r[6]}|SN:{r[9] or '—'}"
            qrcode.make(qr_data).save(path)
            messagebox.showinfo("บันทึกสำเร็จ", f"QR Code บันทึกที่:\n{path}")


# ── Add Equipment Dialog ───────────────────────────────────────

class AddEquipDialog(ctk.CTkToplevel):
    def __init__(self, master, db: DB, on_save=None):
        super().__init__(master)
        self.db = db
        self._on_save = on_save
        self.title("เพิ่ม Equipment ใหม่")
        w, h = 560, 560
        self.geometry(self._center(w, h))
        self.configure(fg_color=T.BG_MAIN)
        self.grab_set()
        self._cats = db.fetch_categories()
        self._build()

    def _center(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        return f"{w}x{h}+{x}+{y}"

    def _field(self, parent, lbl_text, width=460):
        small_label(parent, lbl_text).pack(anchor="w", pady=(10, 3))
        e = entry(parent, width=width)
        e.pack(fill="x")
        return e

    def _build(self):
        label(self, "➕  เพิ่ม Equipment", 18, True).pack(pady=(20, 0), padx=24, anchor="w")

        f = card(self)
        f.pack(fill="both", expand=True, padx=20, pady=12)
        inner = ctk.CTkScrollableFrame(f, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=12)

        # Tag ID + Asset No.
        row1 = ctk.CTkFrame(inner, fg_color="transparent")
        row1.pack(fill="x")
        c1 = ctk.CTkFrame(row1, fg_color="transparent")
        c1.pack(side="left", fill="x", expand=True, padx=(0, 8))
        small_label(c1, "TAG ID *").pack(anchor="w", pady=(0, 3))
        self._tag  = entry(c1, "EQ-001")
        self._tag.pack(fill="x")

        c2 = ctk.CTkFrame(row1, fg_color="transparent")
        c2.pack(side="left", fill="x", expand=True)
        small_label(c2, "ASSET NUMBER").pack(anchor="w", pady=(0, 3))
        self._asset = entry(c2, "AST-2025-001")
        self._asset.pack(fill="x")

        # Category
        small_label(inner, "CATEGORY").pack(anchor="w", pady=(12, 3))
        cat_opts = ["— ไม่ระบุ —"] + [f"{c[3]} {c[1]}" for c in self._cats]
        self._cat_cb = combo(inner, cat_opts, width=460)
        self._cat_cb.pack(fill="x")

        # Name
        small_label(inner, "ชื่อ EQUIPMENT *").pack(anchor="w", pady=(12, 3))
        self._name = entry(inner, "Digital Multimeter")
        self._name.pack(fill="x")

        # Brand + Model
        row2 = ctk.CTkFrame(inner, fg_color="transparent")
        row2.pack(fill="x", pady=(12, 0))
        c3 = ctk.CTkFrame(row2, fg_color="transparent")
        c3.pack(side="left", fill="x", expand=True, padx=(0, 8))
        small_label(c3, "BRAND").pack(anchor="w", pady=(0, 3))
        self._brand = entry(c3, "Fluke")
        self._brand.pack(fill="x")

        c4 = ctk.CTkFrame(row2, fg_color="transparent")
        c4.pack(side="left", fill="x", expand=True)
        small_label(c4, "MODEL").pack(anchor="w", pady=(0, 3))
        self._model = entry(c4, "87V")
        self._model.pack(fill="x")

        # Serial
        small_label(inner, "SERIAL NUMBER").pack(anchor="w", pady=(12, 3))
        self._serial = entry(inner, "SN-XXXXXXX")
        self._serial.pack(fill="x")

        # Description
        small_label(inner, "DESCRIPTION").pack(anchor="w", pady=(12, 3))
        self._desc = entry(inner, "รายละเอียดเพิ่มเติม...")
        self._desc.pack(fill="x")

        # Error label
        self._err = label(self, "", 12, color=T.RED)
        self._err.pack()

        # Buttons
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=(0, 16))
        ghost_btn(btn_row, "ยกเลิก", self.destroy).pack(side="left", padx=(0, 8))
        primary_btn(btn_row, "💾  บันทึก", self._save).pack(side="left")

    def _save(self):
        tag  = self._tag.get().strip()
        name = self._name.get().strip()
        if not tag or not name:
            self._err.configure(text="⚠  กรุณากรอก Tag ID และ ชื่อ Equipment")
            return

        sel = self._cat_cb.get()
        cat_id = None
        for c in self._cats:
            if f"{c[3]} {c[1]}" == sel:
                cat_id = c[0]; break

        ok = self.db.add_equipment(
            tag, self._asset.get().strip(),
            cat_id, name,
            self._brand.get().strip(), self._model.get().strip(),
            self._serial.get().strip(), self._desc.get().strip()
        )
        if ok:
            if self._on_save:
                self._on_save()
            self.destroy()
        else:
            self._err.configure(text="✗  บันทึกไม่สำเร็จ (Tag ID อาจซ้ำ)")


# ═══════════════════════════════════════════════════════════════
#  PAGE: CALIBRATION
# ═══════════════════════════════════════════════════════════════

CAL_COLS = [
    ("Tag",    "Tag ID",     90,  "w"),
    ("Name",   "Equipment", 180,  "w"),
    ("Last",   "Last Cal",  100,  "center"),
    ("Due",    "Cal Due",   100,  "center"),
    ("Days",   "Days Left",  80,  "center"),
    ("Status", "Status",    110,  "center"),
    ("CalBy",  "Cal By",    120,  "w"),
    ("Cert",   "Cert No.",  110,  "w"),
]

class CalibrationPage(ctk.CTkFrame):
    def __init__(self, master, db: DB):
        super().__init__(master, fg_color=T.BG_MAIN)
        self.db = db
        self._all_rows = []
        self._build()
        self._load()

    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=26, pady=(26, 0))
        label(hdr, "Calibration Records", 22, True).pack(side="left")
        primary_btn(hdr, "➕  บันทึก Cal", self._open_add).pack(side="right")

        # Filter bar
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=26, pady=(12, 0))

        self._sv = tk.StringVar()
        self._sv.trace_add("write", lambda *_: self._filter())
        se = entry(bar, "🔍  ค้นหา...", width=240)
        se.configure(textvariable=self._sv)
        se.pack(side="left")

        self._status_cb = combo(bar, ["All Status", "OK", "Due Soon", "Overdue", "No Cal"],
                                width=150)
        self._status_cb.pack(side="left", padx=(10, 0))
        self._status_cb.configure(command=lambda _: self._filter())

        ghost_btn(bar, "🔄 Refresh", self._load).pack(side="left", padx=(10, 0))
        self._count_lbl = label(bar, "", 11, color=T.TEXT2)
        self._count_lbl.pack(side="right")

        # Table
        tc = card(self)
        tc.pack(fill="both", expand=True, padx=26, pady=(12, 26))
        self._tree = build_treeview(tc, CAL_COLS)

    def _load(self):
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self):
        rows = self.db.fetch_equipment_status()
        self._all_rows = rows
        self.after(0, self._render, rows)

    def _filter(self):
        kw  = self._sv.get().lower()
        sel = self._status_cb.get()
        result = []
        for r in self._all_rows:
            if kw and kw not in (r[1] or "").lower() \
                   and kw not in (r[6] or "").lower():
                continue
            days = r[16]
            if sel == "OK"       and not (days is not None and days > 30): continue
            if sel == "Due Soon" and not (days is not None and 0 <= days <= 30): continue
            if sel == "Overdue"  and not (days is not None and days < 0): continue
            if sel == "No Cal"   and days is not None: continue
            result.append(r)
        self._render(result)

    def _render(self, rows):
        self._tree.delete(*self._tree.get_children())
        for i, r in enumerate(rows):
            days = r[16]
            status_txt, clr, _ = cal_status(days)
            values = (
                r[1], r[6],
                str(r[13]) if r[13] else "—",
                str(r[14]) if r[14] else "—",
                str(days) if days is not None else "—",
                status_txt,
                r[15+1] if len(r) > 16 else "—",   # CalBy
                r[15] or "—",                        # CertNo
            )
            tags = ["alt"] if i % 2 == 0 else []
            if days is None:      tags.append("no_cal")
            elif days < 0:        tags.append("overdue")
            elif days <= 30:      tags.append("due_soon")
            else:                 tags.append("ok")
            self._tree.insert("", "end", values=values, tags=tags)
        self._count_lbl.configure(text=f"{len(rows)} รายการ")

    def _open_add(self):
        AddCalDialog(self, self.db, on_save=self._load)


# ── Add Calibration Dialog ────────────────────────────────────

class AddCalDialog(ctk.CTkToplevel):
    def __init__(self, master, db: DB, on_save=None):
        super().__init__(master)
        self.db = db
        self._on_save = on_save
        self.title("บันทึก Calibration")
        w, h = 520, 500
        self.geometry(self._center(w, h))
        self.configure(fg_color=T.BG_MAIN)
        self.grab_set()
        self._equip = db.fetch_equipment_status()
        self._build()

    def _center(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        return f"{w}x{h}+{x}+{y}"

    def _build(self):
        label(self, "📅  บันทึก Calibration", 18, True).pack(pady=(20, 0), padx=24, anchor="w")

        f = card(self)
        f.pack(fill="both", expand=True, padx=20, pady=12)
        inner = ctk.CTkFrame(f, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=18, pady=18)

        # Equipment selector
        small_label(inner, "EQUIPMENT *").pack(anchor="w", pady=(0, 3))
        eq_names = [f"{r[1]} — {r[6]}" for r in self._equip]
        self._eq_cb = combo(inner, eq_names or ["(ไม่มีข้อมูล)"], width=460)
        self._eq_cb.pack(fill="x")

        # Dates row
        dr = ctk.CTkFrame(inner, fg_color="transparent")
        dr.pack(fill="x", pady=(12, 0))

        lc = ctk.CTkFrame(dr, fg_color="transparent")
        lc.pack(side="left", fill="x", expand=True, padx=(0, 8))
        small_label(lc, "CAL DATE *  (YYYY-MM-DD)").pack(anchor="w", pady=(0, 3))
        self._cal_date = entry(lc, date.today().isoformat())
        self._cal_date.pack(fill="x")

        rc = ctk.CTkFrame(dr, fg_color="transparent")
        rc.pack(side="left", fill="x", expand=True)
        small_label(rc, "DUE DATE *  (YYYY-MM-DD)").pack(anchor="w", pady=(0, 3))
        due_default = (date.today() + timedelta(days=365)).isoformat()
        self._due_date = entry(rc, due_default)
        self._due_date.pack(fill="x")

        # Cal by
        small_label(inner, "CALIBRATE BY / LAB").pack(anchor="w", pady=(12, 3))
        self._cal_by = entry(inner, "Delta Cal Lab / ชื่อผู้ทำ")
        self._cal_by.pack(fill="x")

        # Cert no
        small_label(inner, "CERTIFICATE NO.").pack(anchor="w", pady=(12, 3))
        self._cert = entry(inner, "CERT-2025-XXX")
        self._cert.pack(fill="x")

        # Remark
        small_label(inner, "REMARK").pack(anchor="w", pady=(12, 3))
        self._remark = entry(inner, "หมายเหตุ...")
        self._remark.pack(fill="x")

        self._err = label(self, "", 12, color=T.RED)
        self._err.pack()

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=(0, 16))
        ghost_btn(btn_row, "ยกเลิก", self.destroy).pack(side="left", padx=(0, 8))
        primary_btn(btn_row, "💾  บันทึก", self._save).pack(side="left")

    def _save(self):
        sel = self._eq_cb.get()
        eq_id = None
        for r in self._equip:
            if f"{r[1]} — {r[6]}" == sel:
                eq_id = r[0]; break

        if not eq_id:
            self._err.configure(text="⚠  กรุณาเลือก Equipment")
            return

        cal_d = self._cal_date.get().strip()
        due_d = self._due_date.get().strip()
        if not cal_d or not due_d:
            self._err.configure(text="⚠  กรุณากรอกวันที่ให้ครบ")
            return

        ok = self.db.add_calibration(
            eq_id, cal_d, due_d,
            self._cal_by.get().strip(),
            self._cert.get().strip(),
            self._remark.get().strip()
        )
        if ok:
            if self._on_save:
                self._on_save()
            self.destroy()
        else:
            self._err.configure(text="✗  บันทึกไม่สำเร็จ")


# ═══════════════════════════════════════════════════════════════
#  PAGE: SETTINGS
# ═══════════════════════════════════════════════════════════════

class SettingsPage(ctk.CTkFrame):
    def __init__(self, master, db: DB):
        super().__init__(master, fg_color=T.BG_MAIN)
        self.db = db
        self._build()

    def _build(self):
        label(self, "⚙  Settings", 22, True).pack(
            pady=(26, 0), padx=26, anchor="w")
        label(self, "ตั้งค่าการเชื่อมต่อ SQL Server",
              12, color=T.TEXT2).pack(padx=26, anchor="w", pady=(2, 16))

        # DB Connection card
        dc = card(self)
        dc.pack(fill="x", padx=26)
        inner = ctk.CTkFrame(dc, fg_color="transparent")
        inner.pack(fill="x", padx=22, pady=18)

        label(inner, "SQL Server Connection", 14, True).pack(anchor="w", pady=(0, 14))

        def row(lbl, val):
            f = ctk.CTkFrame(inner, fg_color="transparent")
            f.pack(fill="x", pady=4)
            label(f, lbl, 11, color=T.TEXT2, width=140).pack(side="left")
            e = entry(f, width=300)
            e.pack(side="left")
            e.insert(0, val)
            return e

        self._e_server = row("Server", self.db.SQLSERVER.get("server", ""))
        self._e_db     = row("Database", self.db.SQLSERVER.get("database", ""))
        self._e_driver = row("ODBC Driver", self.db.SQLSERVER.get("driver", "ODBC Driver 17 for SQL Server"))

        self._conn_status = label(inner, "", 12)
        self._conn_status.pack(anchor="w", pady=(12, 0))

        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(anchor="w", pady=(10, 0))
        primary_btn(btn_row, "🔌  ทดสอบ & เชื่อมต่อ", self._test_conn).pack(side="left")
        ghost_btn(btn_row, "SQLite Demo", self._use_sqlite).pack(side="left", padx=(10, 0))

        # Info card
        ic = card(self)
        ic.pack(fill="x", padx=26, pady=(14, 0))
        tips = [
            "💡  เปลี่ยน Server/Database แล้วกด 'ทดสอบ & เชื่อมต่อ'",
            "🔐  ใช้ Windows Authentication (Trusted_Connection=yes)",
            "📦  SQLite Demo Mode: ไม่ต้องติดตั้ง SQL Server ก็ใช้ได้",
            "🏷️  ต้องติดตั้ง 'qrcode[pil]' และ 'pillow' เพื่อพิมพ์ QR Code",
        ]
        for t in tips:
            label(ic, t, 12, color=T.TEXT2).pack(anchor="w", padx=20, pady=(8, 0))
        ctk.CTkLabel(ic, text="").pack(pady=4)

    def _test_conn(self):
        self.db.SQLSERVER["server"]   = self._e_server.get().strip()
        self.db.SQLSERVER["database"] = self._e_db.get().strip()
        self.db.SQLSERVER["driver"]   = self._e_driver.get().strip()
        self._conn_status.configure(text="⏳  กำลังเชื่อมต่อ...", text_color=T.ORANGE)
        self.update()
        threading.Thread(target=self._do_connect, daemon=True).start()

    def _do_connect(self):
        ok = self.db.connect_sqlserver()
        def update():
            if ok:
                self._conn_status.configure(
                    text=f"● Connected — {self.db.SQLSERVER['server']}",
                    text_color=T.GREEN)
            else:
                self._conn_status.configure(
                    text="✗  เชื่อมต่อไม่สำเร็จ — ตรวจสอบ Server / Driver / Network",
                    text_color=T.RED)
        self.after(0, update)

    def _use_sqlite(self):
        self.db.close()
        self.db.connect_sqlite()
        self._conn_status.configure(text="● SQLite Demo Mode", text_color=T.BLUE)


# ═══════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ═══════════════════════════════════════════════════════════════

class MainWin(ctk.CTk):
    def __init__(self, db: DB, user: dict):
        super().__init__()
        self.db = db
        self.user = user
        ctk.set_appearance_mode("dark")
        self.title(f"Equipment Management — {user['username']}  [{user['role'].upper()}]")
        w, h = 1050, 680
        self.geometry(self._center(w, h))
        self.minsize(860, 560)
        self.configure(fg_color=T.BG_MAIN)
        self._cur_page = None
        self._build()
        self._nav("dashboard")

    def _center(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        return f"{w}x{h}+{x}+{y}"

    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = Sidebar(self, on_nav=self._nav, user=self.user)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        self._area = ctk.CTkFrame(self, fg_color=T.BG_MAIN, corner_radius=0)
        self._area.grid(row=0, column=1, sticky="nsew")
        self._area.grid_rowconfigure(0, weight=1)
        self._area.grid_columnconfigure(0, weight=1)

    def _nav(self, key: str):
        if self._cur_page:
            self._cur_page.destroy()
        builders = {
            "dashboard":   lambda: DashboardPage(self._area, self.db, self.user),
            "equipment":   lambda: EquipmentPage(self._area, self.db),
            "calibration": lambda: CalibrationPage(self._area, self.db),
            "settings":    lambda: SettingsPage(self._area, self.db),
        }
        page = builders.get(key, builders["dashboard"])()
        page.grid(row=0, column=0, sticky="nsew")
        self._cur_page = page
        self.sidebar.set_active(key)


# ═══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    db = DB()
    mode = db.connect()

    if mode == "failed":
        messagebox.showerror("Error", "ไม่สามารถเชื่อมต่อฐานข้อมูลได้เลย")
        return

    # Login
    login = LoginWin(db)
    login.mainloop()

    if login.logged_user:
        app = MainWin(db, login.logged_user)
        app.mainloop()

    db.close()


if __name__ == "__main__":
    main()
