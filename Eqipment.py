"""
Asset Inventory Viewer — TE-CDBU1
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
อ่านข้อมูลจาก Master_Asset_Report.csv (TSV)
- Primary  : \\10.150.208.54\shopfloor$\testdata\2026\06\AssetInventory\Master_Asset_Report.csv
- Fallback : GitHub raw URL (สำรองเมื่อ network ไม่ได้)

Columns:
  ScanDate | TesterID | ProductModel | Line | StationGroup
  DTNo | AssetNo | AssetType | GPIB_Address | ParentSerialNo
  Vendor | Model | SerialNo | Firmware | Channels

Features:
  • Auto-reload ทุก 60 วินาที (real-time)
  • Search กรอง + filter AssetType / Line / Station
  • Tree view: Instrument → Module ลูก
  • Summary cards: Total / Instrument / Module / Vendor count
  • Export filtered data to CSV
  • Highlight row ที่ serial ผิดปกติ (scientific notation)
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv
import io
import os
import threading
import platform
import socket
import urllib.request
from datetime import datetime
from collections import defaultdict

# ═══════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════

UNC_PATH    = r"\\10.150.208.54\shopfloor$\testdata\2026\06\AssetInventory\Master_Asset_Report.csv"
GITHUB_URL  = "https://raw.githubusercontent.com/TE-CD01/Dashboard/refs/heads/main/Master_Asset_Report.csv"
RELOAD_SEC  = 60      # auto-reload interval


# ═══════════════════════════════════════════════════════════════
#  THEME
# ═══════════════════════════════════════════════════════════════

class T:
    BG_MAIN   = "#111315"
    BG_SIDE   = "#1A1D20"
    BG_CARD   = "#212529"
    BG_INPUT  = "#2C3035"
    BG_HOVER  = "#2A2D32"
    BG_ROW    = "#1C1F23"
    BG_SEL    = "#003D5C"
    BG_INST   = "#0D1F35"   # instrument row tint
    BG_MOD    = "#1A2010"   # module row tint

    BLUE      = "#00B0FF"
    BLUE_DK   = "#0090D6"
    BLUE_DIM  = "#002640"
    GREEN     = "#00E676"
    GREEN_DIM = "#0D2818"
    RED       = "#FF5252"
    ORANGE    = "#FF9100"
    PURPLE    = "#CE93D8"
    TEAL      = "#00BFA5"

    TEXT      = "#E8EAED"
    TEXT2     = "#9AA0A6"
    TEXT3     = "#5F6368"
    FONT      = "Segoe UI"
    R         = 10
    R_SM      = 6


# ═══════════════════════════════════════════════════════════════
#  CSV LOADER
# ═══════════════════════════════════════════════════════════════

COLUMNS = [
    "ScanDate", "TesterID", "ProductModel", "Line", "StationGroup",
    "DTNo", "AssetNo", "AssetType", "GPIB_Address", "ParentSerialNo",
    "Vendor", "Model", "SerialNo", "Firmware", "Channels"
]

def _parse_tsv(raw_text: str) -> list[dict]:
    rows = []
    reader = csv.DictReader(io.StringIO(raw_text), delimiter="\t")
    for row in reader:
        # Normalize keys (strip BOM / whitespace)
        clean = {k.strip().lstrip("\ufeff"): (v or "").strip() for k, v in row.items()}
        rows.append(clean)
    return rows

def load_csv() -> tuple[list[dict], str, str]:
    """
    Returns (rows, source_label, error_msg)
    Tries UNC path first, falls back to GitHub URL.
    """
    # ── Try UNC path ────────────────────────────────────────────
    try:
        if os.path.exists(UNC_PATH):
            with open(UNC_PATH, "r", encoding="utf-8-sig") as f:
                rows = _parse_tsv(f.read())
            return rows, f"📁  {UNC_PATH}", ""
    except Exception as e:
        unc_err = str(e)
    else:
        unc_err = "Path not reachable"

    # ── Fallback: GitHub URL ────────────────────────────────────
    try:
        req = urllib.request.Request(
            GITHUB_URL,
            headers={"User-Agent": "TE-CDBU1-AssetViewer/1.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8-sig")
        rows = _parse_tsv(raw)
        return rows, f"🌐  GitHub (fallback)  [{GITHUB_URL.split('/')[-1]}]", f"UNC unreachable: {unc_err}"
    except Exception as e:
        return [], "", f"UNC: {unc_err}  |  GitHub: {e}"


# ═══════════════════════════════════════════════════════════════
#  SHARED WIDGETS
# ═══════════════════════════════════════════════════════════════

def lbl(master, text, size=13, bold=False, color=None, **kw):
    return ctk.CTkLabel(master, text=text,
                        font=(T.FONT, size, "bold" if bold else "normal"),
                        text_color=color or T.TEXT, **kw)

def card(master, **kw):
    return ctk.CTkFrame(master, fg_color=T.BG_CARD, corner_radius=T.R, **kw)

def small_lbl(master, text, **kw):
    return ctk.CTkLabel(master, text=text, font=(T.FONT, 10, "bold"),
                        text_color=T.TEXT2, **kw)

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

def stat_card(parent, value, sublabel, color, col, row=0):
    f = ctk.CTkFrame(parent, fg_color=T.BG_CARD, corner_radius=T.R)
    f.grid(row=row, column=col, padx=(0, 10), pady=4, sticky="ew")
    ctk.CTkLabel(f, text=str(value), font=(T.FONT, 30, "bold"),
                 text_color=color).pack(pady=(12, 0))
    ctk.CTkLabel(f, text=sublabel, font=(T.FONT, 10),
                 text_color=T.TEXT2).pack(pady=(2, 10))
    return f

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
    tree.column("#0", width=30, minwidth=30, stretch=False)   # tree expand icon col

    for col_id, col_name, col_w, anchor in columns:
        tree.heading(col_id, text=col_name,
                     command=lambda c=col_id: sort_tree(tree, c, False))
        tree.column(col_id, width=col_w, minwidth=max(col_w-20, 40), anchor=anchor)

    vsb = ttk.Scrollbar(wrap, orient="vertical",   command=tree.yview)
    hsb = ttk.Scrollbar(wrap, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    hsb.grid(row=1, column=0, sticky="ew")
    wrap.grid_rowconfigure(0, weight=1)
    wrap.grid_columnconfigure(0, weight=1)

    # Tags
    tree.tag_configure("inst",   background="#0D1F2D", foreground=T.BLUE)
    tree.tag_configure("mod",    background="#0E1A0E", foreground=T.GREEN)
    tree.tag_configure("alt",    background=T.BG_ROW)
    tree.tag_configure("warn",   foreground=T.ORANGE)
    tree.tag_configure("normal", foreground=T.TEXT)

    return tree

_sort_reverse: dict = {}
def sort_tree(tree, col, reverse):
    data = [(tree.set(k, col), k) for k in tree.get_children("")]
    try:
        data.sort(key=lambda x: float(x[0]) if x[0].replace('.','',1).isdigit() else x[0].lower(),
                  reverse=reverse)
    except Exception:
        data.sort(key=lambda x: x[0].lower(), reverse=reverse)
    for i, (_, k) in enumerate(data):
        tree.move(k, "", i)
    tree.heading(col, command=lambda: sort_tree(tree, col, not reverse))


# ═══════════════════════════════════════════════════════════════
#  MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════

# Table columns definition
TREE_COLS = [
    ("ScanDate",      "Scan Date",     130, "w"),
    ("TesterID",      "Tester ID",      80, "center"),
    ("ProductModel",  "Product Model", 120, "w"),
    ("Line",          "Line",           55, "center"),
    ("StationGroup",  "Station Group", 110, "w"),
    ("AssetType",     "Type",           80, "center"),
    ("GPIB_Address",  "GPIB",           55, "center"),
    ("Vendor",        "Vendor",        160, "w"),
    ("Model",         "Model",         130, "w"),
    ("SerialNo",      "Serial No.",    150, "w"),
    ("Firmware",      "Firmware",       90, "center"),
    ("Channels",      "Channels",       70, "center"),
    ("AssetNo",       "Asset No.",      80, "center"),
    ("DTNo",          "DT No.",         70, "center"),
]

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

        self._all_rows: list[dict] = []
        self._filtered: list[dict] = []
        self._source   = ""
        self._err      = ""
        self._loading  = False
        self._reload_job = None
        self._last_load  = None

        # Filter state
        self._sv_search    = tk.StringVar()
        self._sv_type      = tk.StringVar(value="All Types")
        self._sv_line      = tk.StringVar(value="All Lines")
        self._sv_station   = tk.StringVar(value="All Stations")
        self._sv_vendor    = tk.StringVar(value="All Vendors")
        self._tree_mode    = tk.BooleanVar(value=True)   # True = Instrument→Module tree

        self._build_ui()
        self._load_data()

    # ── Layout ────────────────────────────────────────────────

    def _center(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        return f"{w}x{h}+{x}+{y}"

    def _build_ui(self):
        # ── Top bar ─────────────────────────────────────────
        topbar = ctk.CTkFrame(self, fg_color=T.BG_SIDE, corner_radius=0, height=54)
        topbar.pack(fill="x", side="top")
        topbar.pack_propagate(False)

        tb_inner = ctk.CTkFrame(topbar, fg_color="transparent")
        tb_inner.pack(fill="both", expand=True, padx=18, pady=8)

        # Logo
        cvs = tk.Canvas(tb_inner, width=32, height=32,
                        bg=T.BG_SIDE, highlightthickness=0)
        cvs.pack(side="left")
        cvs.create_oval(2, 2, 30, 30, fill=T.BLUE, outline="")
        cvs.create_text(16, 16, text="⚙", fill="#000", font=(T.FONT, 12, "bold"))

        lbl(tb_inner, "Asset Inventory Viewer", 15, True).pack(side="left", padx=(10, 0))
        lbl(tb_inner, "TE-CDBU1  •  Delta Electronics (Thailand)", 10,
            color=T.TEXT2).pack(side="left", padx=(10, 0), pady=2)

        # Source + time label (right side)
        self._src_lbl = lbl(tb_inner, "", 10, color=T.TEXT2)
        self._src_lbl.pack(side="right")
        self._time_lbl = lbl(tb_inner, "", 11, color=T.TEXT3)
        self._time_lbl.pack(side="right", padx=(0, 16))

        # ── Summary cards ───────────────────────────────────
        self._card_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._card_frame.pack(fill="x", padx=18, pady=(14, 0))
        for i in range(6):
            self._card_frame.grid_columnconfigure(i, weight=1, uniform="c")

        # placeholder cards
        self._cards = {}
        card_defs = [
            ("total",      "📦  Total Rows",      T.BLUE),
            ("instrument", "🔌  Instruments",      T.TEAL),
            ("module",     "🧩  Modules",           T.GREEN),
            ("vendors",    "🏭  Vendors",            T.PURPLE),
            ("stations",   "🖥  Stations",           T.ORANGE),
            ("scandate",   "🕐  Last Scan",          T.TEXT2),
        ]
        for col, (key, sub, color) in enumerate(card_defs):
            f = ctk.CTkFrame(self._card_frame, fg_color=T.BG_CARD,
                             corner_radius=T.R)
            f.grid(row=0, column=col, padx=(0, 8), pady=2, sticky="ew")
            v = ctk.CTkLabel(f, text="—", font=(T.FONT, 26, "bold"),
                             text_color=color)
            v.pack(pady=(10, 0))
            ctk.CTkLabel(f, text=sub, font=(T.FONT, 10),
                         text_color=T.TEXT2).pack(pady=(2, 8))
            self._cards[key] = v

        # ── Status bar (source / error) ─────────────────────
        self._status_bar = ctk.CTkFrame(self, fg_color=T.BG_INPUT,
                                        corner_radius=T.R_SM, height=28)
        self._status_bar.pack(fill="x", padx=18, pady=(8, 0))
        self._status_bar.pack_propagate(False)
        self._status_lbl = lbl(self._status_bar, "กำลังโหลด...", 11,
                               color=T.TEXT2)
        self._status_lbl.pack(side="left", padx=12, pady=4)
        self._err_lbl = lbl(self._status_bar, "", 11, color=T.RED)
        self._err_lbl.pack(side="right", padx=12, pady=4)

        # ── Filter toolbar ──────────────────────────────────
        fbar = ctk.CTkFrame(self, fg_color="transparent")
        fbar.pack(fill="x", padx=18, pady=(8, 0))

        # Search
        self._se = search_entry(fbar, "🔍  ค้นหา Vendor / Model / Serial / TesterID...",
                                width=320)
        self._se.configure(textvariable=self._sv_search)
        self._se.pack(side="left")
        self._sv_search.trace_add("write", lambda *_: self._apply_filter())

        # Filter combos
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
            cb.configure(variable=sv,
                         command=lambda _: self._apply_filter())
            cb.pack(side="left", padx=(8, 0))

        # Right-side buttons
        accent_btn(fbar, "🔄  Reload", self._load_data,
                   width=100, color=T.TEAL).pack(side="right")
        ghost_btn(fbar,  "💾  Export CSV", self._export,
                  width=110).pack(side="right", padx=(0, 8))
        ghost_btn(fbar,  "🌳  Tree / Flat",
                  self._toggle_tree_mode,
                  width=110).pack(side="right", padx=(0, 8))

        # Count label
        self._count_lbl = lbl(fbar, "", 11, color=T.TEXT2)
        self._count_lbl.pack(side="right", padx=(0, 10))

        # ── Tree view ───────────────────────────────────────
        tree_card = card(self)
        tree_card.pack(fill="both", expand=True, padx=18, pady=(8, 14))
        self._tree = build_tree(tree_card, TREE_COLS, height=24)
        self._tree.bind("<Double-1>", self._on_dbl)

        # ── Reload countdown ────────────────────────────────
        self._countdown_lbl = lbl(self, "", 10, color=T.TEXT3)
        self._countdown_lbl.pack(pady=(0, 4))
        self._countdown_sec = RELOAD_SEC
        self._tick_countdown()

    # ── Data Loading ──────────────────────────────────────────

    def _load_data(self):
        if self._loading:
            return
        self._loading = True
        self._status_lbl.configure(text="⏳  กำลังโหลดข้อมูล...", text_color=T.ORANGE)
        self._err_lbl.configure(text="")
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self):
        rows, source, err = load_csv()
        self.after(0, self._on_loaded, rows, source, err)

    def _on_loaded(self, rows, source, err):
        self._loading   = False
        self._all_rows  = rows
        self._source    = source
        self._err       = err
        self._last_load = datetime.now()

        # Update status bar
        if source:
            src_short = source[:80] + "…" if len(source) > 80 else source
            self._status_lbl.configure(text=src_short, text_color=T.TEXT2)
        else:
            self._status_lbl.configure(text="❌  โหลดไม่สำเร็จ", text_color=T.RED)
        if err:
            self._err_lbl.configure(text=f"⚠  {err[:80]}")

        # Update time label
        if self._last_load:
            self._time_lbl.configure(
                text=f"อัปเดต: {self._last_load.strftime('%H:%M:%S')}")

        # Populate filter combos
        self._rebuild_combos()
        self._apply_filter()
        self._update_cards()

        # Reset countdown
        self._countdown_sec = RELOAD_SEC

    def _rebuild_combos(self):
        rows = self._all_rows
        types    = sorted({r.get("AssetType", "") for r in rows} - {""})
        lines    = sorted({r.get("Line", "")      for r in rows} - {""})
        stations = sorted({r.get("StationGroup","") for r in rows} - {""})
        vendors  = sorted({r.get("Vendor", "")    for r in rows} - {""})

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
        rows = self._all_rows
        n_inst    = sum(1 for r in rows if r.get("AssetType") == "Instrument")
        n_mod     = sum(1 for r in rows if r.get("AssetType") == "Module")
        vendors   = {r.get("Vendor","") for r in rows} - {""}
        stations  = {r.get("StationGroup","") for r in rows} - {""}
        scan_times = [r.get("ScanDate","") for r in rows if r.get("ScanDate")]
        last_scan = max(scan_times) if scan_times else "—"

        self._cards["total"     ].configure(text=str(len(rows)))
        self._cards["instrument"].configure(text=str(n_inst))
        self._cards["module"    ].configure(text=str(n_mod))
        self._cards["vendors"   ].configure(text=str(len(vendors)))
        self._cards["stations"  ].configure(text=str(len(stations)))
        self._cards["scandate"  ].configure(text=last_scan[:16] if last_scan != "—" else "—")

    # ── Filtering ─────────────────────────────────────────────

    def _apply_filter(self):
        kw      = self._sv_search.get().lower()
        f_type  = self._sv_type.get()
        f_line  = self._sv_line.get()
        f_st    = self._sv_station.get()
        f_ven   = self._sv_vendor.get()

        result = []
        for r in self._all_rows:
            if f_type not in ("All Types", "")    and r.get("AssetType")    != f_type: continue
            if f_line not in ("All Lines", "")    and r.get("Line")          != f_line: continue
            if f_st   not in ("All Stations", "") and r.get("StationGroup")  != f_st:   continue
            if f_ven  not in ("All Vendors", "")  and r.get("Vendor")        != f_ven:  continue
            if kw:
                searchable = " ".join([
                    r.get("Vendor",""), r.get("Model",""),
                    r.get("SerialNo",""), r.get("TesterID",""),
                    r.get("ProductModel",""), r.get("AssetNo",""),
                    r.get("StationGroup",""), r.get("Firmware",""),
                ]).lower()
                if kw not in searchable:
                    continue
            result.append(r)

        self._filtered = result
        self._count_lbl.configure(text=f"{len(result)} รายการ")

        if self._tree_mode.get():
            self._render_tree(result)
        else:
            self._render_flat(result)

    def _render_tree(self, rows: list[dict]):
        """Render Instrument → Module hierarchy"""
        tree = self._tree
        tree.delete(*tree.get_children(""))

        # Group instruments; modules hang off their ParentSerialNo
        instruments = [r for r in rows if r.get("AssetType") == "Instrument"]
        modules     = [r for r in rows if r.get("AssetType") == "Module"]
        others      = [r for r in rows if r.get("AssetType") not in ("Instrument", "Module")]

        mod_by_parent = defaultdict(list)
        for m in modules:
            mod_by_parent[m.get("ParentSerialNo", "")].append(m)

        for i, inst in enumerate(instruments):
            sn  = inst.get("SerialNo", "")
            iid = f"inst_{i}"
            vals = self._row_values(inst)
            tag  = "inst"
            tree.insert("", "end", iid=iid, text="▶",
                        values=vals, tags=(tag,), open=True)

            children = mod_by_parent.get(sn, [])
            for j, mod in enumerate(children):
                ciid = f"mod_{i}_{j}"
                cvals = self._row_values(mod)
                tree.insert(iid, "end", iid=ciid, text="  └",
                            values=cvals, tags=("mod",))

        # Other types (not Instrument/Module)
        for i, r in enumerate(others):
            tag = "alt" if i % 2 == 0 else "normal"
            tree.insert("", "end", text="", values=self._row_values(r), tags=(tag,))

    def _render_flat(self, rows: list[dict]):
        """Render flat table (no hierarchy)"""
        tree = self._tree
        tree.delete(*tree.get_children(""))
        for i, r in enumerate(rows):
            asset_type = r.get("AssetType", "")
            if asset_type == "Instrument":
                tag = "inst"
            elif asset_type == "Module":
                tag = "mod"
            else:
                tag = "alt" if i % 2 == 0 else "normal"
            # Highlight suspicious serial (scientific notation from Excel)
            sn = r.get("SerialNo", "")
            if "E+" in sn or "e+" in sn:
                tag = "warn"
            tree.insert("", "end", text="", values=self._row_values(r), tags=(tag,))

    def _row_values(self, r: dict) -> tuple:
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

    # ── Tree mode toggle ──────────────────────────────────────

    def _toggle_tree_mode(self):
        self._tree_mode.set(not self._tree_mode.get())
        self._apply_filter()

    # ── Double-click detail ───────────────────────────────────

    def _on_dbl(self, event):
        iid = self._tree.focus()
        if not iid:
            return
        vals = self._tree.item(iid, "values")
        if not vals:
            return
        # Map values back to dict
        col_ids = [c[0] for c in TREE_COLS]
        row_dict = dict(zip(col_ids, vals))
        DetailPopup(self, row_dict)

    # ── Export ────────────────────────────────────────────────

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
            writer = csv.DictWriter(f, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(self._filtered)
        messagebox.showinfo("Export สำเร็จ", f"บันทึก {len(self._filtered)} rows ที่:\n{path}")

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
                text=f"Auto-reload ใน {self._countdown_sec}s",
                text_color=clr)
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
        self.title(f"Detail — {row.get('SerialNo','?')}")
        w, h = 560, 560
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
        asset_type = row.get("AssetType", "—")
        color = T.BLUE if asset_type == "Instrument" else T.GREEN

        lbl(self, f"{row.get('Vendor','—')}  {row.get('Model','—')}",
            18, True).pack(pady=(20, 0), padx=24, anchor="w")
        lbl(self, f"{asset_type}  •  S/N: {row.get('SerialNo','—')}",
            12, color=color).pack(padx=24, anchor="w", pady=(2, 14))

        f = ctk.CTkFrame(self, fg_color=T.BG_CARD, corner_radius=T.R)
        f.pack(fill="both", expand=True, padx=20, pady=(0, 14))
        inner = ctk.CTkScrollableFrame(f, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=14)

        field_map = [
            ("Scan Date",      "ScanDate"),
            ("Tester ID",      "TesterID"),
            ("Product Model",  "ProductModel"),
            ("Line",           "Line"),
            ("Station Group",  "StationGroup"),
            ("DT No.",         "DTNo"),
            ("Asset No.",      "AssetNo"),
            ("Asset Type",     "AssetType"),
            ("GPIB Address",   "GPIB_Address"),
            ("Parent S/N",     "ParentSerialNo"),
            ("Vendor",         "Vendor"),
            ("Model",          "Model"),
            ("Serial No.",     "SerialNo"),
            ("Firmware",       "Firmware"),
            ("Channels",       "Channels"),
        ]
        for i, (label_text, key) in enumerate(field_map):
            val = row.get(key, "—") or "—"
            row_bg = T.BG_HOVER if i % 2 == 0 else "transparent"
            rf = ctk.CTkFrame(inner, fg_color=row_bg, corner_radius=4)
            rf.pack(fill="x", pady=1)
            lbl(rf, label_text, 11, color=T.TEXT2, width=130, anchor="w"
                ).pack(side="left", padx=(10, 0), pady=6)
            val_color = T.ORANGE if ("E+" in val or "e+" in val) else T.TEXT
            lbl(rf, val, 12, color=val_color).pack(side="left", padx=8)

        # Warn if serial looks like scientific notation
        sn = row.get("SerialNo", "")
        if "E+" in sn or "e+" in sn:
            warn_f = ctk.CTkFrame(self, fg_color="#2A1A00", corner_radius=T.R_SM)
            warn_f.pack(fill="x", padx=20, pady=(0, 6))
            lbl(warn_f,
                "⚠  Serial No. อาจแสดงผลผิดพลาดเนื่องจาก Excel แปลงเป็น Scientific Notation\n"
                "   กรุณาตรวจสอบในไฟล์ CSV โดยตรง",
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
