"""
Asset Inventory Viewer — TE-CDBU1  v4
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Local/UNC only — ไม่มี internet

NEW in v4:
  [+] เพิ่ม Asset ใหม่ (➕ Add)
  [+] แก้ไข Asset ที่มีอยู่ (✏️ Edit — double-click หรือ right-click)
  [+] ลบ Asset (🗑 Delete — right-click หรือปุ่ม)
  [+] บันทึกกลับไฟล์ต้นทาง UNC โดยตรง (save_csv)
  [+] ตั้งค่า Path / Reload interval (⚙ Settings)
  [+] Right-click context menu บน tree
  [+] Backup อัตโนมัติก่อนเขียนทับ (.bak)
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv
import io
import os
import shutil
import threading
from datetime import datetime
from collections import defaultdict

# ═══════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════

CSV_PATH   = r"\\10.150.208.54\shopfloor$\testdata\2026\06\AssetInventory\Master_Asset_Report.csv"
RELOAD_SEC = 60


# ═══════════════════════════════════════════════════════════════
#  THEME
# ═══════════════════════════════════════════════════════════════

class T:
    BG_MAIN  = "#111315"
    BG_SIDE  = "#1A1D20"
    BG_CARD  = "#212529"
    BG_INPUT = "#2C3035"
    BG_HOVER = "#2A2D32"
    BG_ROW   = "#1C1F23"
    BG_SEL   = "#003D5C"

    BLUE     = "#00B0FF"
    BLUE_DK  = "#0090D6"
    GREEN    = "#00E676"
    RED      = "#FF5252"
    ORANGE   = "#FF9100"
    PURPLE   = "#CE93D8"
    TEAL     = "#00BFA5"

    TEXT     = "#E8EAED"
    TEXT2    = "#9AA0A6"
    TEXT3    = "#5F6368"
    FONT     = "Segoe UI"
    R        = 10
    R_SM     = 6


# ═══════════════════════════════════════════════════════════════
#  COLUMNS (canonical names used internally)
# ═══════════════════════════════════════════════════════════════

COLUMNS = [
    "ScanDate", "TesterID", "ProductModel", "Line", "StationGroup",
    "DTNo", "AssetNo", "AssetType", "GPIB_Address", "ParentSerialNo",
    "Vendor", "Model", "SerialNo", "Firmware", "Channels",
]

# Map possible header variants → canonical name
#   key = lower-stripped header from file
#   value = canonical column name
HEADER_ALIASES = {
    "scandate":       "ScanDate",
    "testerid":       "TesterID",
    "productmodel":   "ProductModel",
    "line":           "Line",
    "stationgroup":   "StationGroup",
    "dtno":           "DTNo",
    "assetno":        "AssetNo",
    "assettype":      "AssetType",
    "gpib_address":   "GPIB_Address",
    "gpib_addr":      "GPIB_Address",   # ← alias ที่ไฟล์จริงใช้
    "gpibaddress":    "GPIB_Address",
    "gpib":           "GPIB_Address",
    "parentserialno": "ParentSerialNo",
    "parentserial":   "ParentSerialNo",
    "vendor":         "Vendor",
    "model":          "Model",
    "serialno":       "SerialNo",
    "serial":         "SerialNo",
    "firmware":       "Firmware",
    "channels":       "Channels",
}


def _fix_serial(val: str) -> str:
    """
    Excel มักแปลง Serial เช่น 6334A0013941 → 6.3344E+11
    พยายามแปลงกลับ: ถ้าเป็น scientific notation ให้แปลงเป็น int string
    """
    val = val.strip()
    if not val:
        return val
    try:
        f = float(val)
        # ถ้าค่าเป็น int จริง ๆ (ไม่มีทศนิยม) ให้แปลงกลับ
        if f == int(f) and ("E" in val.upper() or "e" in val):
            return str(int(f))
    except (ValueError, OverflowError):
        pass
    return val


def _detect_delimiter(sample: str) -> str:
    """ตรวจ delimiter จาก 2-3 บรรทัดแรก"""
    for line in sample.splitlines()[:3]:
        tabs   = line.count("\t")
        commas = line.count(",")
        semis  = line.count(";")
        if tabs >= commas and tabs >= semis and tabs > 0:
            return "\t"
        if commas >= tabs and commas >= semis and commas > 0:
            return ","
        if semis > 0:
            return ";"
    return "\t"   # default


def _parse_csv(raw_text: str) -> list[dict]:
    """
    อ่าน CSV/TSV → list of dict ที่ใช้ canonical column names
    รองรับ BOM, delimiter อัตโนมัติ, alias headers, serial fix
    """
    # ลบ BOM
    raw_text = raw_text.lstrip("\ufeff")

    delim = _detect_delimiter(raw_text)
    reader = csv.DictReader(io.StringIO(raw_text), delimiter=delim)

    # Build header map
    if reader.fieldnames is None:
        return []

    header_map: dict[str, str] = {}
    for h in reader.fieldnames:
        clean = h.strip().lstrip("\ufeff").lower().replace(" ", "").replace("_", "")
        # ลอง exact lower match ก่อน
        canonical = HEADER_ALIASES.get(
            h.strip().lstrip("\ufeff").lower(),
            HEADER_ALIASES.get(clean, h.strip())   # fallback to clean version
        )
        header_map[h] = canonical

    rows = []
    for raw_row in reader:
        row: dict[str, str] = {}
        for orig_key, value in raw_row.items():
            if orig_key is None:
                continue
            canonical = header_map.get(orig_key, orig_key)
            row[canonical] = (value or "").strip()

        # Fix serial numbers that Excel mangled into scientific notation
        if "SerialNo" in row:
            row["SerialNo"] = _fix_serial(row["SerialNo"])

        # Fix ParentSerialNo as well
        if "ParentSerialNo" in row:
            row["ParentSerialNo"] = _fix_serial(row["ParentSerialNo"])

        rows.append(row)

    return rows


def _read_file_with_encoding(path: str) -> str:
    """ลอง encoding หลายแบบตามลำดับ"""
    for enc in ("utf-8-sig", "utf-8", "cp874", "cp1252", "latin-1"):
        try:
            with open(path, "r", encoding=enc, errors="strict") as f:
                return f.read()
        except (UnicodeDecodeError, LookupError):
            continue
    # last resort
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def load_local() -> tuple[list[dict], str]:
    """
    โหลดจาก CSV_PATH (local / UNC) เท่านั้น — ไม่มี internet fallback
    Returns (rows, error_message)   error ว่าง = สำเร็จ
    """
    try:
        if not os.path.isfile(CSV_PATH):
            return [], f"ไม่พบไฟล์:\n{CSV_PATH}"
        raw  = _read_file_with_encoding(CSV_PATH)
        rows = _parse_csv(raw)
        return rows, ""
    except PermissionError:
        return [], f"ไม่มีสิทธิ์เข้าถึงไฟล์:\n{CSV_PATH}"
    except OSError as e:
        return [], f"OS Error: {e}\nPath: {CSV_PATH}"
    except Exception as e:
        return [], f"Error: {e}"


def save_csv(rows: list[dict]) -> str:
    """
    เขียน rows กลับไปที่ CSV_PATH โดยตรง
    - Backup ไฟล์เดิมเป็น .bak ก่อนเสมอ
    - Returns error string (ว่าง = สำเร็จ)
    """
    try:
        # Backup ก่อนเขียนทับ
        if os.path.isfile(CSV_PATH):
            bak = CSV_PATH + ".bak"
            shutil.copy2(CSV_PATH, bak)

        # ตรวจ delimiter ของไฟล์เดิม (ถ้ามี) เพื่อใช้ให้ตรงกัน
        delim = "\t"
        if os.path.isfile(CSV_PATH):
            try:
                sample = _read_file_with_encoding(CSV_PATH)
                delim  = _detect_delimiter(sample)
            except Exception:
                pass

        with open(CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS,
                                    extrasaction="ignore", delimiter=delim)
            writer.writeheader()
            writer.writerows(rows)
        return ""
    except PermissionError:
        return f"ไม่มีสิทธิ์เขียนไฟล์:\n{CSV_PATH}"
    except OSError as e:
        return f"OS Error: {e}"
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════
#  UI HELPERS
# ═══════════════════════════════════════════════════════════════

def lbl(master, text, size=13, bold=False, color=None, **kw):
    return ctk.CTkLabel(master, text=text,
                        font=(T.FONT, size, "bold" if bold else "normal"),
                        text_color=color or T.TEXT, **kw)

def card(master, **kw):
    return ctk.CTkFrame(master, fg_color=T.BG_CARD, corner_radius=T.R, **kw)

def search_entry(master, placeholder="🔍  Search...", width=260, **kw):
    return ctk.CTkEntry(master, placeholder_text=placeholder,
                        fg_color=T.BG_INPUT, border_color=T.BG_HOVER,
                        text_color=T.TEXT, font=(T.FONT, 13),
                        corner_radius=T.R_SM, height=36, width=width, **kw)

def ghost_btn(master, text, cmd, width=100, **kw):
    return ctk.CTkButton(master, text=text, command=cmd,
                         fg_color=T.BG_HOVER, hover_color=T.BG_INPUT,
                         text_color=T.TEXT2, font=(T.FONT, 12),
                         corner_radius=T.R_SM, height=34, width=width, **kw)

def accent_btn(master, text, cmd, width=120, color=None, **kw):
    return ctk.CTkButton(master, text=text, command=cmd,
                         fg_color=color or T.BLUE, hover_color=T.BLUE_DK,
                         text_color="#000", font=(T.FONT, 12, "bold"),
                         corner_radius=T.R_SM, height=34, width=width, **kw)

def mk_combo(master, values, width=160, **kw):
    return ctk.CTkComboBox(master, values=values,
                           fg_color=T.BG_INPUT, border_color=T.BG_HOVER,
                           button_color=T.BG_HOVER, button_hover_color=T.BLUE,
                           text_color=T.TEXT, font=(T.FONT, 12),
                           dropdown_fg_color=T.BG_CARD,
                           dropdown_text_color=T.TEXT,
                           corner_radius=T.R_SM, height=34, width=width, **kw)

def build_tree(parent, columns: list[tuple], height=22) -> ttk.Treeview:
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("A.Treeview",
                    background=T.BG_CARD, foreground=T.TEXT,
                    fieldbackground=T.BG_CARD, rowheight=30,
                    font=(T.FONT, 12), borderwidth=0, relief="flat")
    style.configure("A.Treeview.Heading",
                    background=T.BG_INPUT, foreground=T.TEXT2,
                    font=(T.FONT, 10, "bold"), relief="flat")
    style.map("A.Treeview",
              background=[("selected", T.BG_SEL)],
              foreground=[("selected", T.BLUE)])
    style.map("A.Treeview.Heading",
              background=[("active", T.BG_HOVER)])

    wrap = ctk.CTkFrame(parent, fg_color="transparent")
    wrap.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    col_ids = [c[0] for c in columns]
    tree = ttk.Treeview(wrap, columns=col_ids, show="tree headings",
                        style="A.Treeview", height=height)
    tree.column("#0", width=30, minwidth=30, stretch=False)

    for col_id, col_name, col_w, anchor in columns:
        tree.heading(col_id, text=col_name,
                     command=lambda c=col_id: _sort_tree(tree, c, False))
        tree.column(col_id, width=col_w, minwidth=max(col_w - 20, 40), anchor=anchor)

    vsb = ttk.Scrollbar(wrap, orient="vertical",   command=tree.yview)
    hsb = ttk.Scrollbar(wrap, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    hsb.grid(row=1, column=0, sticky="ew")
    wrap.grid_rowconfigure(0, weight=1)
    wrap.grid_columnconfigure(0, weight=1)

    tree.tag_configure("inst",   background="#0D1F2D", foreground=T.BLUE)
    tree.tag_configure("mod",    background="#0E1A0E", foreground=T.GREEN)
    tree.tag_configure("alt",    background=T.BG_ROW)
    tree.tag_configure("warn",   foreground=T.ORANGE)
    tree.tag_configure("normal", foreground=T.TEXT)
    return tree


def _sort_tree(tree, col, reverse):
    data = [(tree.set(k, col), k) for k in tree.get_children("")]
    try:
        data.sort(
            key=lambda x: float(x[0]) if x[0].replace(".", "", 1).lstrip("-").isdigit() else x[0].lower(),
            reverse=reverse
        )
    except Exception:
        data.sort(key=lambda x: x[0].lower(), reverse=reverse)
    for i, (_, k) in enumerate(data):
        tree.move(k, "", i)
    tree.heading(col, command=lambda: _sort_tree(tree, col, not reverse))


# ═══════════════════════════════════════════════════════════════
#  TABLE COLUMNS
# ═══════════════════════════════════════════════════════════════

TREE_COLS = [
    ("ScanDate",     "Scan Date",     130, "w"),
    ("TesterID",     "Tester ID",      80, "center"),
    ("ProductModel", "Product Model", 120, "w"),
    ("Line",         "Line",           55, "center"),
    ("StationGroup", "Station Group", 110, "w"),
    ("AssetType",    "Type",           80, "center"),
    ("GPIB_Address", "GPIB",           55, "center"),
    ("Vendor",       "Vendor",        160, "w"),
    ("Model",        "Model",         130, "w"),
    ("SerialNo",     "Serial No.",    150, "w"),
    ("Firmware",     "Firmware",       90, "center"),
    ("Channels",     "Channels",       70, "center"),
    ("AssetNo",      "Asset No.",      80, "center"),
    ("DTNo",         "DT No.",         70, "center"),
]


# ═══════════════════════════════════════════════════════════════
#  MAIN APP
# ═══════════════════════════════════════════════════════════════

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Asset Inventory Viewer — TE-CDBU1")
        w, h = 1280, 760
        self.geometry(self._center(w, h))
        self.minsize(1000, 600)
        self.configure(fg_color=T.BG_MAIN)

        self._all_rows:  list[dict] = []
        self._filtered:  list[dict] = []
        self._loading    = False
        self._reload_job = None
        self._last_load  = None

        self._sv_search  = tk.StringVar()
        self._sv_type    = tk.StringVar(value="All Types")
        self._sv_line    = tk.StringVar(value="All Lines")
        self._sv_station = tk.StringVar(value="All Stations")
        self._sv_vendor  = tk.StringVar(value="All Vendors")
        self._tree_mode  = tk.BooleanVar(value=True)

        self._build_ui()
        self._load_data()

    # ── Center window ─────────────────────────────────────────

    def _center(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        return f"{w}x{h}+{x}+{y}"

    # ── Build UI ──────────────────────────────────────────────

    def _build_ui(self):
        # Top bar
        topbar = ctk.CTkFrame(self, fg_color=T.BG_SIDE, corner_radius=0, height=54)
        topbar.pack(fill="x", side="top")
        topbar.pack_propagate(False)
        tb = ctk.CTkFrame(topbar, fg_color="transparent")
        tb.pack(fill="both", expand=True, padx=18, pady=8)

        cvs = tk.Canvas(tb, width=32, height=32, bg=T.BG_SIDE, highlightthickness=0)
        cvs.pack(side="left")
        cvs.create_oval(2, 2, 30, 30, fill=T.BLUE, outline="")
        cvs.create_text(16, 16, text="⚙", fill="#000", font=(T.FONT, 12, "bold"))

        lbl(tb, "Asset Inventory Viewer", 15, True).pack(side="left", padx=(10, 0))
        lbl(tb, "TE-CDBU1  •  Delta Electronics (Thailand)", 10,
            color=T.TEXT2).pack(side="left", padx=(10, 0), pady=2)

        self._time_lbl = lbl(tb, "", 11, color=T.TEXT3)
        self._time_lbl.pack(side="right", padx=(0, 4))
        lbl(tb, "📁  Local", 11, color=T.TEAL).pack(side="right", padx=(0, 12))

        # Summary cards
        self._card_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._card_frame.pack(fill="x", padx=18, pady=(14, 0))
        for i in range(6):
            self._card_frame.grid_columnconfigure(i, weight=1, uniform="c")

        self._cards = {}
        card_defs = [
            ("total",      "📦  Total Rows",   T.BLUE),
            ("instrument", "🔌  Instruments",   T.TEAL),
            ("module",     "🧩  Modules",        T.GREEN),
            ("vendors",    "🏭  Vendors",         T.PURPLE),
            ("stations",   "🖥  Stations",        T.ORANGE),
            ("scandate",   "🕐  Last Scan",       T.TEXT2),
        ]
        for col, (key, sub, color) in enumerate(card_defs):
            f = ctk.CTkFrame(self._card_frame, fg_color=T.BG_CARD, corner_radius=T.R)
            f.grid(row=0, column=col, padx=(0, 8), pady=2, sticky="ew")
            v = ctk.CTkLabel(f, text="—", font=(T.FONT, 26, "bold"), text_color=color)
            v.pack(pady=(10, 0))
            ctk.CTkLabel(f, text=sub, font=(T.FONT, 10), text_color=T.TEXT2).pack(pady=(2, 8))
            self._cards[key] = v

        # Status bar
        self._status_bar = ctk.CTkFrame(self, fg_color=T.BG_INPUT,
                                        corner_radius=T.R_SM, height=28)
        self._status_bar.pack(fill="x", padx=18, pady=(8, 0))
        self._status_bar.pack_propagate(False)
        self._status_lbl = lbl(self._status_bar, "กำลังโหลด...", 11, color=T.TEXT2)
        self._status_lbl.pack(side="left", padx=12, pady=4)
        self._err_lbl = lbl(self._status_bar, "", 11, color=T.RED)
        self._err_lbl.pack(side="right", padx=12, pady=4)

        # Filter toolbar
        fbar = ctk.CTkFrame(self, fg_color="transparent")
        fbar.pack(fill="x", padx=18, pady=(8, 0))

        self._se = search_entry(fbar,
            "🔍  ค้นหา Vendor / Model / Serial / TesterID...", width=320)
        self._se.configure(textvariable=self._sv_search)
        self._se.pack(side="left")
        self._sv_search.trace_add("write", lambda *_: self._apply_filter())

        self._cb_type    = mk_combo(fbar, ["All Types"],    width=130)
        self._cb_line    = mk_combo(fbar, ["All Lines"],    width=110)
        self._cb_station = mk_combo(fbar, ["All Stations"], width=160)
        self._cb_vendor  = mk_combo(fbar, ["All Vendors"],  width=160)

        for cb, sv in [
            (self._cb_type,    self._sv_type),
            (self._cb_line,    self._sv_line),
            (self._cb_station, self._sv_station),
            (self._cb_vendor,  self._sv_vendor),
        ]:
            cb.configure(variable=sv, command=lambda _: self._apply_filter())
            cb.pack(side="left", padx=(8, 0))

        accent_btn(fbar, "🔄  Reload", self._load_data,
                   width=100, color=T.TEAL).pack(side="right")
        ghost_btn(fbar, "💾  Export CSV", self._export,
                  width=110).pack(side="right", padx=(0, 8))
        ghost_btn(fbar, "🌳  Tree / Flat", self._toggle_tree_mode,
                  width=110).pack(side="right", padx=(0, 8))
        ghost_btn(fbar, "⚙  Settings", self._open_settings,
                  width=100).pack(side="right", padx=(0, 8))

        # Add / Delete buttons (left side, after search)
        accent_btn(fbar, "➕  Add", self._add_asset,
                   width=90, color=T.GREEN).pack(side="left", padx=(10, 0))
        ghost_btn(fbar, "🗑  Delete", self._delete_selected,
                  width=90).pack(side="left", padx=(6, 0))

        self._count_lbl = lbl(fbar, "", 11, color=T.TEXT2)
        self._count_lbl.pack(side="right", padx=(0, 10))

        # Tree
        tree_card = card(self)
        tree_card.pack(fill="both", expand=True, padx=18, pady=(8, 6))
        self._tree = build_tree(tree_card, TREE_COLS, height=24)
        self._tree.bind("<Double-1>", self._on_dbl)
        self._tree.bind("<Button-3>", self._on_right_click)   # right-click menu

        # Right-click context menu
        self._ctx_menu = tk.Menu(self, tearoff=0, bg=T.BG_CARD, fg=T.TEXT,
                                 activebackground=T.BG_SEL, activeforeground=T.BLUE,
                                 font=(T.FONT, 11))
        self._ctx_menu.add_command(label="✏️  Edit",   command=self._edit_selected)
        self._ctx_menu.add_command(label="🗑  Delete", command=self._delete_selected)
        self._ctx_menu.add_separator()
        self._ctx_menu.add_command(label="➕  Add New", command=self._add_asset)

        # Countdown
        self._countdown_lbl = lbl(self, "", 10, color=T.TEXT3)
        self._countdown_lbl.pack(pady=(0, 4))
        self._countdown_sec = RELOAD_SEC
        self._tick_countdown()

    # ── Load data ─────────────────────────────────────────────

    def _load_data(self):
        if self._loading:
            return
        self._loading = True
        self._status_lbl.configure(
            text=f"⏳  กำลังโหลด: {CSV_PATH}", text_color=T.ORANGE)
        self._err_lbl.configure(text="")
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self):
        rows, err = load_local()
        self.after(0, self._on_loaded, rows, err)

    def _on_loaded(self, rows: list[dict], err: str):
        self._loading   = False
        self._all_rows  = rows
        self._last_load = datetime.now()

        if err:
            self._status_lbl.configure(text="❌  โหลดไม่สำเร็จ", text_color=T.RED)
            self._err_lbl.configure(text=f"⚠  {err[:120]}")
        else:
            self._status_lbl.configure(
                text=f"✅  {CSV_PATH}", text_color=T.TEXT2)
            self._err_lbl.configure(text="")

        self._time_lbl.configure(
            text=f"อัปเดต: {self._last_load.strftime('%H:%M:%S')}")

        self._rebuild_combos()
        self._apply_filter()
        self._update_cards()
        self._countdown_sec = RELOAD_SEC

    def _rebuild_combos(self):
        rows     = self._all_rows
        types    = sorted({r.get("AssetType",    "") for r in rows} - {""})
        lines    = sorted({r.get("Line",         "") for r in rows} - {""})
        stations = sorted({r.get("StationGroup", "") for r in rows} - {""})
        vendors  = sorted({r.get("Vendor",       "") for r in rows} - {""})

        for cb, opts, sv, default in [
            (self._cb_type,    types,    self._sv_type,    "All Types"),
            (self._cb_line,    lines,    self._sv_line,    "All Lines"),
            (self._cb_station, stations, self._sv_station, "All Stations"),
            (self._cb_vendor,  vendors,  self._sv_vendor,  "All Vendors"),
        ]:
            cb.configure(values=[default] + opts)
            if sv.get() not in ([default] + opts):
                sv.set(default)

    def _update_cards(self):
        rows      = self._all_rows
        n_inst    = sum(1 for r in rows if r.get("AssetType") == "Instrument")
        n_mod     = sum(1 for r in rows if r.get("AssetType") == "Module")
        vendors   = {r.get("Vendor", "") for r in rows} - {""}
        stations  = {r.get("StationGroup", "") for r in rows} - {""}
        scan_times = [r.get("ScanDate", "") for r in rows if r.get("ScanDate")]
        last_scan = max(scan_times) if scan_times else "—"

        self._cards["total"     ].configure(text=str(len(rows)))
        self._cards["instrument"].configure(text=str(n_inst))
        self._cards["module"    ].configure(text=str(n_mod))
        self._cards["vendors"   ].configure(text=str(len(vendors)))
        self._cards["stations"  ].configure(text=str(len(stations)))
        self._cards["scandate"  ].configure(text=last_scan[:12] if last_scan != "—" else "—")

    # ── Filter ────────────────────────────────────────────────

    def _apply_filter(self):
        kw     = self._sv_search.get().lower()
        f_type = self._sv_type.get()
        f_line = self._sv_line.get()
        f_st   = self._sv_station.get()
        f_ven  = self._sv_vendor.get()

        result = []
        for r in self._all_rows:
            if f_type not in ("All Types", "")    and r.get("AssetType")    != f_type: continue
            if f_line not in ("All Lines", "")    and r.get("Line")          != f_line: continue
            if f_st   not in ("All Stations", "") and r.get("StationGroup")  != f_st:   continue
            if f_ven  not in ("All Vendors", "")  and r.get("Vendor")        != f_ven:  continue
            if kw:
                haystack = " ".join([
                    r.get("Vendor", ""), r.get("Model", ""),
                    r.get("SerialNo", ""), r.get("TesterID", ""),
                    r.get("ProductModel", ""), r.get("AssetNo", ""),
                    r.get("StationGroup", ""), r.get("Firmware", ""),
                ]).lower()
                if kw not in haystack:
                    continue
            result.append(r)

        self._filtered = result
        self._count_lbl.configure(text=f"{len(result)} รายการ")

        if self._tree_mode.get():
            self._render_tree(result)
        else:
            self._render_flat(result)

    # ── Render ────────────────────────────────────────────────

    def _render_tree(self, rows: list[dict]):
        tree = self._tree
        tree.delete(*tree.get_children(""))

        instruments = [r for r in rows if r.get("AssetType") == "Instrument"]
        modules     = [r for r in rows if r.get("AssetType") == "Module"]
        others      = [r for r in rows if r.get("AssetType") not in ("Instrument", "Module")]

        # Group modules by ParentSerialNo (strip whitespace for safe matching)
        mod_by_parent: dict[str, list] = defaultdict(list)
        for m in modules:
            key = m.get("ParentSerialNo", "").strip()
            mod_by_parent[key].append(m)

        for i, inst in enumerate(instruments):
            sn  = inst.get("SerialNo", "").strip()
            iid = f"inst_{i}"
            tree.insert("", "end", iid=iid, text="▶",
                        values=self._row_vals(inst), tags=("inst",), open=True)
            for j, mod in enumerate(mod_by_parent.get(sn, [])):
                tree.insert(iid, "end", iid=f"mod_{i}_{j}", text="  └",
                            values=self._row_vals(mod), tags=("mod",))

        for i, r in enumerate(others):
            tag = "alt" if i % 2 == 0 else "normal"
            tree.insert("", "end", text="", values=self._row_vals(r), tags=(tag,))

    def _render_flat(self, rows: list[dict]):
        tree = self._tree
        tree.delete(*tree.get_children(""))
        for i, r in enumerate(rows):
            atype = r.get("AssetType", "")
            tag = ("inst" if atype == "Instrument"
                   else "mod" if atype == "Module"
                   else "alt" if i % 2 == 0 else "normal")
            # Highlight serials that still look scientific (couldn't convert)
            sn = r.get("SerialNo", "")
            if "E+" in sn.upper():
                tag = "warn"
            tree.insert("", "end", text="", values=self._row_vals(r), tags=(tag,))

    def _row_vals(self, r: dict) -> tuple:
        return (
            r.get("ScanDate",     ""),
            r.get("TesterID",     ""),
            r.get("ProductModel", ""),
            r.get("Line",         ""),
            r.get("StationGroup", ""),
            r.get("AssetType",    ""),
            r.get("GPIB_Address", ""),
            r.get("Vendor",       ""),
            r.get("Model",        ""),
            r.get("SerialNo",     ""),
            r.get("Firmware",     ""),
            r.get("Channels",     ""),
            r.get("AssetNo",      ""),
            r.get("DTNo",         ""),
        )

    # ── Toggle tree mode ──────────────────────────────────────

    def _toggle_tree_mode(self):
        self._tree_mode.set(not self._tree_mode.get())
        self._apply_filter()

    # ── Double-click → Edit ───────────────────────────────────

    def _on_dbl(self, _event):
        self._edit_selected()

    # ── Right-click menu ──────────────────────────────────────

    def _on_right_click(self, event):
        iid = self._tree.identify_row(event.y)
        if iid:
            self._tree.selection_set(iid)
            self._tree.focus(iid)
        try:
            self._ctx_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._ctx_menu.grab_release()

    # ── Add Asset ─────────────────────────────────────────────

    def _add_asset(self):
        AssetFormPopup(self, existing_row=None, on_save=self._on_form_save)

    # ── Edit selected Asset ───────────────────────────────────

    def _edit_selected(self):
        iid = self._tree.focus()
        if not iid:
            messagebox.showinfo("ไม่ได้เลือก", "กรุณาเลือกรายการที่ต้องการแก้ไขก่อน")
            return
        vals = self._tree.item(iid, "values")
        if not vals:
            return
        row_dict = dict(zip([c[0] for c in TREE_COLS], vals))
        # Find index in _all_rows by SerialNo + TesterID (unique enough)
        sn  = row_dict.get("SerialNo", "")
        tid = row_dict.get("TesterID", "")
        idx = next((i for i, r in enumerate(self._all_rows)
                    if r.get("SerialNo") == sn and r.get("TesterID") == tid), None)
        AssetFormPopup(self, existing_row=row_dict, row_index=idx,
                       on_save=self._on_form_save)

    def _on_form_save(self, new_row: dict, row_index: int | None):
        """Callback from AssetFormPopup — insert or update then save to file"""
        if row_index is None:
            # Add new
            new_row.setdefault("ScanDate", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            self._all_rows.append(new_row)
        else:
            # Update existing
            self._all_rows[row_index] = new_row

        err = save_csv(self._all_rows)
        if err:
            messagebox.showerror("บันทึกไม่สำเร็จ", err)
        else:
            self._rebuild_combos()
            self._apply_filter()
            self._update_cards()

    # ── Delete selected Asset ─────────────────────────────────

    def _delete_selected(self):
        iid = self._tree.focus()
        if not iid:
            messagebox.showinfo("ไม่ได้เลือก", "กรุณาเลือกรายการที่ต้องการลบก่อน")
            return
        vals = self._tree.item(iid, "values")
        if not vals:
            return
        row_dict = dict(zip([c[0] for c in TREE_COLS], vals))
        sn  = row_dict.get("SerialNo", "—")
        mdl = row_dict.get("Model",    "—")
        if not messagebox.askyesno(
            "ยืนยันการลบ",
            f"ต้องการลบรายการนี้?\n\nModel: {mdl}\nSerial: {sn}\n\n"
            f"⚠ ไฟล์ต้นทางจะถูกแก้ไขโดยตรง (มี .bak backup อัตโนมัติ)"
        ):
            return

        tid = row_dict.get("TesterID", "")
        idx = next((i for i, r in enumerate(self._all_rows)
                    if r.get("SerialNo") == sn and r.get("TesterID") == tid), None)
        if idx is None:
            messagebox.showerror("Error", "ไม่พบรายการในข้อมูล")
            return

        self._all_rows.pop(idx)
        err = save_csv(self._all_rows)
        if err:
            messagebox.showerror("บันทึกไม่สำเร็จ", err)
        else:
            self._rebuild_combos()
            self._apply_filter()
            self._update_cards()

    # ── Settings ──────────────────────────────────────────────

    def _open_settings(self):
        SettingsPopup(self, on_apply=self._on_settings_apply)

    def _on_settings_apply(self, new_path: str, new_reload: int):
        global CSV_PATH, RELOAD_SEC
        CSV_PATH   = new_path
        RELOAD_SEC = new_reload
        self._load_data()

    # ── Export CSV ────────────────────────────────────────────

    def _export(self):
        if not self._filtered:
            messagebox.showwarning("ไม่มีข้อมูล", "ไม่มีข้อมูลสำหรับ export")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=f"AssetExport_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            filetypes=[("CSV", "*.csv")]
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(self._filtered)
        messagebox.showinfo("Export สำเร็จ",
                            f"บันทึก {len(self._filtered)} rows ที่:\n{path}")

    # ── Auto-reload countdown ─────────────────────────────────

    def _tick_countdown(self):
        self._countdown_sec -= 1
        if self._countdown_sec <= 0:
            self._countdown_lbl.configure(text="🔄  Auto-reload...", text_color=T.ORANGE)
            self._load_data()
            self._countdown_sec = RELOAD_SEC
        else:
            clr = T.TEXT3 if self._countdown_sec > 15 else T.ORANGE
            self._countdown_lbl.configure(
                text=f"Auto-reload ใน {self._countdown_sec}s", text_color=clr)
        self._reload_job = self.after(1000, self._tick_countdown)

    def destroy(self):
        if self._reload_job:
            self.after_cancel(self._reload_job)
        super().destroy()


# ═══════════════════════════════════════════════════════════════
#  DETAIL POPUP
# ═══════════════════════════════════════════════════════════════

class DetailPopup(ctk.CTkToplevel):
    def __init__(self, master, row: dict):
        super().__init__(master)
        self.title(f"Detail — {row.get('SerialNo', '?')}")
        w, h = 560, 580
        self.geometry(self._center(w, h))
        self.configure(fg_color=T.BG_MAIN)
        self.grab_set()
        self._build(row)

    def _center(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        return f"{w}x{h}+{x}+{y}"

    def _build(self, row: dict):
        atype = row.get("AssetType", "—")
        color = T.BLUE if atype == "Instrument" else T.GREEN

        lbl(self, f"{row.get('Vendor', '—')}  {row.get('Model', '—')}",
            18, True).pack(pady=(20, 0), padx=24, anchor="w")
        lbl(self, f"{atype}  •  S/N: {row.get('SerialNo', '—')}",
            12, color=color).pack(padx=24, anchor="w", pady=(2, 14))

        f = ctk.CTkFrame(self, fg_color=T.BG_CARD, corner_radius=T.R)
        f.pack(fill="both", expand=True, padx=20, pady=(0, 6))
        inner = ctk.CTkScrollableFrame(f, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=14)

        fields = [
            ("Scan Date",     "ScanDate"),
            ("Tester ID",     "TesterID"),
            ("Product Model", "ProductModel"),
            ("Line",          "Line"),
            ("Station Group", "StationGroup"),
            ("DT No.",        "DTNo"),
            ("Asset No.",     "AssetNo"),
            ("Asset Type",    "AssetType"),
            ("GPIB Address",  "GPIB_Address"),
            ("Parent S/N",    "ParentSerialNo"),
            ("Vendor",        "Vendor"),
            ("Model",         "Model"),
            ("Serial No.",    "SerialNo"),
            ("Firmware",      "Firmware"),
            ("Channels",      "Channels"),
        ]
        for i, (label_text, key) in enumerate(fields):
            val = row.get(key, "—") or "—"
            bg  = T.BG_HOVER if i % 2 == 0 else "transparent"
            rf  = ctk.CTkFrame(inner, fg_color=bg, corner_radius=4)
            rf.pack(fill="x", pady=1)
            lbl(rf, label_text, 11, color=T.TEXT2, width=130, anchor="w"
                ).pack(side="left", padx=(10, 0), pady=6)
            val_color = T.ORANGE if ("E+" in val.upper()) else T.TEXT
            lbl(rf, val, 12, color=val_color).pack(side="left", padx=8)

        sn = row.get("SerialNo", "")
        if "E+" in sn.upper():
            wf = ctk.CTkFrame(self, fg_color="#2A1A00", corner_radius=T.R_SM)
            wf.pack(fill="x", padx=20, pady=(0, 6))
            lbl(wf,
                "⚠  Serial No. อาจแสดงผิดจาก Excel Scientific Notation\n"
                "   ระบบพยายามแปลงกลับแล้ว — กรุณาตรวจสอบในไฟล์ต้นฉบับด้วย",
                11, color=T.ORANGE).pack(padx=14, pady=8)

        ctk.CTkButton(self, text="ปิด", command=self.destroy,
                      fg_color=T.BG_HOVER, hover_color=T.BG_INPUT,
                      text_color=T.TEXT2, font=(T.FONT, 12),
                      corner_radius=T.R_SM, height=34).pack(pady=(0, 14))


# ═══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = App()
    app.mainloop()
