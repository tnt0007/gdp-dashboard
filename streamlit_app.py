"""
نظام أوامر التحميل وحركة السائقين (Dispatch & Drivers Movement ERP)
النسخة المستقرة المربوطة مركزياً بقواعد بيانات (COO) و (HR)
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import sqlite3, pandas as pd, os, shutil, re, webbrowser, threading
from datetime import datetime, timedelta

HAS_PIL = False
try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    try:
        import subprocess, sys
        subprocess.run([sys.executable, "-m", "pip", "install", "Pillow", "-q", "--user"], capture_output=True, timeout=60)
        from PIL import Image, ImageTk
        HAS_PIL = True
    except: pass

# ══════════════════════════════════════════════════════════════
# ✅ تحديد المسار الديناميكي (المرساة المركزية لـ OneDrive)
# ══════════════════════════════════════════════════════════════
USER_HOME = os.path.expanduser("~")
_P1 = os.path.join(USER_HOME, "OneDrive - al hamad aluminum extrusions", "22-02-2022", "ERP")
_P2 = os.path.join(USER_HOME, "OneDrive - al hamad aluminum extrusions", "haitham seddiqi's files - 22-02-2022", "ERP")
try:    _P3 = os.path.dirname(os.path.abspath(__file__))
except: _P3 = os.getcwd()

BASE_DIR = _P3
for _p in [_P1, _P2, _P3]:
    if os.path.exists(_p) and os.path.exists(os.path.join(_p, "confirmation_orders.db")):
        BASE_DIR = _p; break

DB_COO       = os.path.join(BASE_DIR, "confirmation_orders.db")
DB_HR        = os.path.join(BASE_DIR, "factory_erp.db")
DB_MOVEMENT  = os.path.join(BASE_DIR, "drivers_movement.db")
BACKUP_DIR   = os.path.join(BASE_DIR, "Drivers_Backups")
EMP_PIC_DIR  = os.path.join(BASE_DIR, "pic")
LOGO_PATH    = os.path.join(BASE_DIR, "logo2.jpg")
LOGO_UP_PATH = os.path.join(BASE_DIR, "logo UP.jpg")
LOGO_D_PATH  = os.path.join(BASE_DIR, "logo D.jpg")

os.makedirs(BACKUP_DIR, exist_ok=True)

def format_date_std(d_str):
    """توحيد صيغة التواريخ الصارمة dd-Mon-yyyy"""
    if not d_str or str(d_str).lower() in ("nan", "none", ""): return ""
    clean_d = str(d_str).split()[0].replace("/", "-")
    for fmt in ["%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"]:
        try: return datetime.strptime(clean_d, fmt).strftime("%d-%b-%Y")
        except: continue
    return clean_d

def setup_movement_db():
    conn = sqlite3.connect(DB_MOVEMENT, timeout=10000)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS dispatch_slips (
        slip_no TEXT PRIMARY KEY, slip_date TEXT, driver_name TEXT,
        customer_name TEXT, destination_area TEXT, co_reference TEXT,
        vehicle_number TEXT, status TEXT, remarks TEXT,
        created_by TEXT, created_timestamp TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS audit_trail (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, action TEXT,
        timestamp TEXT, details TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS company_vehicles (plate_no TEXT PRIMARY KEY)''')
    if c.execute("SELECT COUNT(*) FROM company_vehicles").fetchone()[0] == 0:
        for v in ["TRUCK - 7412", "PICKUP - 9632", "TESLA - 3", "HIACE - 8520"]:
            c.execute("INSERT INTO company_vehicles VALUES (?)", (v,))
    conn.commit(); conn.close()

setup_movement_db()

class ScrollableFrame(tk.Frame):
    def __init__(self, parent, bg="#f5f6fa", **kw):
        super().__init__(parent, bg=bg, **kw)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.sc_y = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.sc_y.pack(side=tk.RIGHT, fill=tk.Y); self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas.configure(yscrollcommand=self.sc_y.set); self.inner = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self._win, width=e.width))
        for w in [self, self.inner]:
            w.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._on_wheel))
            w.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))
    def _on_wheel(self, e):
        try:
            widget = self.winfo_containing(e.x_root, e.y_root)
            if widget and str(widget).startswith(str(self)) and "treeview" not in str(widget).lower() and "text" not in str(widget).lower():
                self.canvas.yview_scroll(int(-1*(e.delta/120)), "units")
        except: pass

# ══════════════════════════════════════════════════════════════
# شاشة الدخول (تتصل بـ COO Database مباشرة)
# ══════════════════════════════════════════════════════════════
class LoginWindow:
    def __init__(self, root):
        self.root = root; self.root.title("دخول السائقين | Dispatch Login"); self.root.geometry("450x520")
        self.root.configure(bg="#f5f6fa"); self.root.resizable(False, False)
        self.root.geometry(f"+{self.root.winfo_screenwidth()//2-225}+{self.root.winfo_screenheight()//2-260}")
        
        card = tk.Frame(self.root, bg="white", bd=1, relief="solid"); card.place(relx=.5, rely=.5, anchor="center", width=380, height=460)
        if os.path.exists(LOGO_PATH) and HAS_PIL:
            try:
                img = Image.open(LOGO_PATH).resize((130,100),Image.Resampling.LANCZOS); ph = ImageTk.PhotoImage(img)
                lbl = tk.Label(card, image=ph, bg="white"); lbl.image=ph; lbl.pack(pady=(25,8))
            except: pass
        tk.Label(card, text="نظام حركة السائقين\nDrivers Dispatch ERP", font=("ae_AlMothnna",14,"bold"), bg="white", fg="#2c3e50").pack(pady=8)
        tk.Label(card, text="اسم المستخدم | Username", font=("ae_AlMothnna",10,"bold"), bg="white").pack(pady=(14,0))
        self.eu = ttk.Entry(card, font=("Arial",12), justify="center", width=25); self.eu.pack(pady=4)
        tk.Label(card, text="كلمة المرور | Password", font=("ae_AlMothnna",10,"bold"), bg="white").pack(pady=(8,0))
        self.ep = ttk.Entry(card, font=("Arial",12), show="*", justify="center", width=25); self.ep.pack(pady=4)
        self.ep.bind("<Return>", lambda e: self._login())
        tk.Button(card, text="دخول | Login 🔐", font=("ae_AlMothnna",12,"bold"), bg="#2980b9", fg="white", width=20, command=self._login).pack(pady=25)

    def _login(self):
        u = self.eu.get().strip(); p = self.ep.get().strip()
        if not u or not p: return messagebox.showwarning("تنبيه", "أدخل البيانات.")
        if not os.path.exists(DB_COO): return messagebox.showerror("خطأ", f"قاعدة COO مفقودة في:\n{DB_COO}")
        
        try:
            conn = sqlite3.connect(DB_COO, timeout=5)
            r_auth = conn.execute("SELECT role FROM app_users WHERE username=? AND password=?", (u, p)).fetchone()
            conn.close()
        except Exception as e: return messagebox.showerror("خطأ", str(e))

        if r_auth:
            emp_name_en = u.upper()
            if os.path.exists(DB_HR):
                try:
                    c_hr = sqlite3.connect(DB_HR, timeout=5).cursor()
                    r_hr = c_hr.execute("SELECT name, name_ar FROM employees WHERE emp_id=?", (u,)).fetchone()
                    if r_hr:
                        fn = r_hr[0] if r_hr[0] else r_hr[1]
                        emp_name_en = str(fn).split()[0].upper() if fn else u.upper()
                except: pass
            self.root.destroy(); main = tk.Tk(); DispatchMovementApp(main, u, emp_name_en, r_auth[0]); main.mainloop()
        else: messagebox.showerror("خطأ", "بيانات الدخول غير مطابقة لنظام COO.")

# ══════════════════════════════════════════════════════════════
# التطبيق الرئيسي
# ══════════════════════════════════════════════════════════════
class DispatchMovementApp:
    def __init__(self, root, username, real_name, role):
        self.root = root; self.username = username; self.real_name = real_name; self.role = role
        self.root.title("نظام حركة السائقين وإدارة التوصيل | Al Hamad Dispatch ERP"); self.root.state("zoomed")
        self.root.rowconfigure(0, weight=1); self.root.columnconfigure(0, weight=1)

        # التزام صارم بالألوان المعيارية (بدون وضع داكن)
        self.bg_main = "#f5f6fa"; self.bg_sec = "#ffffff"; self.fg_main = "#333333"; self.en_color = "#95a5a6"; self.lbl_color = "#555555"
        self.c_pri = "#3498db"; self.c_suc = "#27ae60"; self.c_dan = "#e74c3c"; self.c_warn = "#f39c12"; self.c_dark = "#2c3e50"
        
        self.ar_font = ("ae_AlMothnna", 11); self.ar_bold = ("ae_AlMothnna", 11, "bold")
        self.en_font = ("Arial", 9); self.lbl_font = ("ae_AlMothnna", 9); self.title_font = ("ae_AlMothnna", 12, "bold")

        self.customers_dict = {}; self.drivers_list = []; self.vehicles_list = []
        self.emp_pic_path = self._find_pic(self.username)

        self._apply_theme(); self._fetch_live_data(); self._build_ui(); self._reset_slip_form()
        threading.Thread(target=self._auto_backup, daemon=True).start()

    def _apply_theme(self):
        self.root.configure(bg=self.bg_main); s = ttk.Style(); s.theme_use("default")
        s.configure("TNotebook", background=self.bg_main); s.configure("TNotebook.Tab", font=self.ar_bold, padding=[8,4])
        s.configure("Treeview.Heading", font=self.lbl_font, foreground=self.lbl_color, background="#dcdde1")
        s.configure("Treeview", font=self.en_font, foreground=self.fg_main, rowheight=26, background=self.bg_sec, fieldbackground=self.bg_sec)
        s.map("Treeview", background=[("selected","#d9ebf9")], foreground=[("selected","#333")])

    def _find_pic(self, emp_id):
        for ext in [".jpg", ".jpeg", ".png", ".JPG", ".PNG"]:
            p = os.path.join(EMP_PIC_DIR, f"{emp_id}{ext}")
            if os.path.exists(p): return p
        return None

    def _fetch_live_data(self):
        """سحب الداتا الحية من الـ COO والـ HR"""
        # 1. العملاء ومناطقهم
        if os.path.exists(DB_COO):
            try:
                conn = sqlite3.connect(DB_COO, timeout=5)
                for r in conn.execute("SELECT name, area FROM customers WHERE name IS NOT NULL ORDER BY name").fetchall():
                    self.customers_dict[str(r[0]).strip()] = str(r[1] or "").strip()
                conn.close()
            except: pass

        # 2. السائقين (بالإنجليزية UPPERCASE)
        if os.path.exists(DB_HR):
            try:
                conn_hr = sqlite3.connect(DB_HR, timeout=5)
                cols = [c[1].lower() for c in conn_hr.execute("PRAGMA table_info(employees)").fetchall()]
                where = "status NOT LIKE '%كنسل%'"
                if "designation" in cols: where += " AND (designation LIKE '%driver%' OR designation LIKE '%سائق%')"
                elif "job_title" in cols: where += " AND (job_title LIKE '%driver%' OR job_title LIKE '%سائق%')"
                else: where += " AND (name LIKE '%driver%' OR name_ar LIKE '%سائق%')"

                for eid, nen, nar in conn_hr.execute(f"SELECT emp_id, name, name_ar FROM employees WHERE {where}").fetchall():
                    dn = str(nen).strip() if nen else str(nar).strip()
                    dn = dn.split()[0].upper() if dn else str(eid)
                    self.drivers_list.append(f"{eid} - {dn}")
                conn_hr.close()
            except: pass
        if not self.drivers_list: self.drivers_list = ["101 - JAMEEL", "102 - RAFIQ", "103 - KHALID"]

        # 3. السيارات
        try:
            conn_m = sqlite3.connect(DB_MOVEMENT, timeout=5)
            self.vehicles_list = [r[0] for r in conn_m.execute("SELECT plate_no FROM company_vehicles ORDER BY plate_no").fetchall()]
            conn_m.close()
        except: self.vehicles_list = ["TRUCK - 7412"]

    def _build_ui(self):
        top = tk.Frame(self.root, bg=self.c_dark, height=56); top.pack(fill=tk.X); top.pack_propagate(False)
        pf = tk.Frame(top, bg=self.c_dark); pf.pack(side=tk.LEFT, padx=15, pady=4)
        if self.emp_pic_path and HAS_PIL:
            try:
                img = Image.open(self.emp_pic_path).resize((44,44), Image.Resampling.LANCZOS); ph = ImageTk.PhotoImage(img)
                lbl = tk.Label(pf, image=ph, bg=self.c_dark); lbl.image = ph; lbl.pack(side=tk.LEFT, padx=4)
            except: pass
        tk.Label(pf, text=f"User | {self.real_name}", font=self.title_font, bg=self.c_dark, fg="#f1c40f").pack(side=tk.LEFT, padx=4)
        tk.Label(top, text="إدارة حركة السائقين وأذونات التحميل | Dispatch & Drivers ERP", font=self.title_font, bg=self.c_dark, fg="white").pack(side=tk.RIGHT, padx=15)

        self.nb = ttk.Notebook(self.root); self.nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.tab_form = tk.Frame(self.nb, bg=self.bg_main); self.nb.add(self.tab_form, text="إصدار إذن توصيل | Delivery Slip")
        self.tab_hist = tk.Frame(self.nb, bg=self.bg_main); self.nb.add(self.tab_hist, text="سجل الحركة | Dispatch History")

        self._build_slip_tab(); self._build_history_tab()

    def _build_slip_tab(self):
        sf = ScrollableFrame(self.tab_form, bg=self.bg_main); sf.pack(fill=tk.BOTH, expand=True); P = sf.inner
        card = tk.LabelFrame(P, text=" تفاصيل إذن التحميل | Slip Details ", font=self.ar_bold, bg=self.bg_sec, fg=self.lbl_color)
        card.pack(fill=tk.X, padx=12, pady=8, ipadx=6, ipady=6)
        for i in range(5): card.columnconfigure(i, weight=1)

        def lbl(r, c, txt, **k): tk.Label(card, text=txt, font=self.lbl_font, bg=self.bg_sec, fg=self.lbl_color, **k).grid(row=r, column=c, sticky="e", padx=6, pady=4)
        def ent(r, c, w=22): e=ttk.Entry(card, font=self.en_font, width=w); e.grid(row=r, column=c, sticky="w", padx=6, pady=4); return e

        # Row 0
        lbl(0, 0, "رقم الإذن | Slip No"); self.slip_ent = ent(0, 1)
        lbl(0, 2, "التاريخ | Date"); self.date_ent = ent(0, 3); self.date_ent.insert(0, datetime.now().strftime("%d-%b-%Y"))
        
        # Row 1: Driver + Picture box
        lbl(1, 0, "السائق | Driver Name", fg=self.c_pri)
        self.drv_cb = ttk.Combobox(card, font=self.en_font, width=20, values=self.drivers_list)
        self.drv_cb.grid(row=1, column=1, sticky="w", padx=6, pady=4)
        
        pic_f = tk.Frame(card, width=75, height=75, bg="#ecf0f1", bd=1, relief="solid")
        pic_f.grid(row=0, column=4, rowspan=3, padx=10, pady=4); pic_f.grid_propagate(False)
        self.lbl_drv_pic = tk.Label(pic_f, text="صورة\nالسائق", bg="#ecf0f1", font=self.lbl_font, fg="#7f8c8d")
        self.lbl_drv_pic.pack(expand=True, fill=tk.BOTH)

        def _preview_driver(*a):
            val = self.drv_cb.get().strip()
            if val and " - " in val:
                p = self._find_pic(val.split(" - ")[0])
                if p and HAS_PIL:
                    try:
                        img = Image.open(p).resize((71, 71), Image.Resampling.LANCZOS); ph = ImageTk.PhotoImage(img)
                        self.lbl_drv_pic.config(image=ph, text=""); self.lbl_drv_pic.image = ph; return
                    except: pass
            self.lbl_drv_pic.config(image="", text="لا توجد صورة")
        self.drv_cb.bind("<<ComboboxSelected>>", _preview_driver); self.drv_cb.bind("<FocusOut>", _preview_driver)

        lbl(1, 2, "رقم السيارة | Vehicle Plate"); self.veh_cb = ttk.Combobox(card, font=self.en_font, width=20, values=self.vehicles_list)
        self.veh_cb.grid(row=1, column=3, sticky="w", padx=6, pady=4)

        # Row 2: Customer + auto Area
        lbl(2, 0, "العميل | Customer Name")
        self.cust_cb = ttk.Combobox(card, font=self.en_font, width=20, values=list(self.customers_dict.keys()))
        self.cust_cb.grid(row=2, column=1, sticky="w", padx=6, pady=4)

        lbl(2, 2, "المنطقة | Destination Area")
        self.area_ent = ent(2, 3)

        def _autofill_area(*a):
            c_name = self.cust_cb.get().strip()
            if c_name in self.customers_dict:
                self.area_ent.delete(0, tk.END); self.area_ent.insert(0, self.customers_dict[c_name])
        self.cust_cb.bind("<<ComboboxSelected>>", _autofill_area)

        # Row 3
        lbl(3, 0, "رقم طلبية المصنع | COO Ref No"); self.co_ref_ent = ent(3, 1)
        lbl(3, 2, "حالة الرحلة | Trip Status")
        self.status_var = tk.StringVar(value="Out for Delivery")
        st_f = tk.Frame(card, bg=self.bg_sec); st_f.grid(row=3, column=3, columnspan=2, sticky="w", padx=6, pady=4)
        for t, v in [("🚚 قيد التوصيل", "Out for Delivery"), ("✅ تم التوصيل", "Delivered"), ("❌ إلغاء", "Cancelled")]:
            tk.Radiobutton(st_f, text=t, variable=self.status_var, value=v, font=self.lbl_font, bg=self.bg_sec).pack(side=tk.LEFT, padx=4)

        # Row 4: Remarks
        lbl(4, 0, "تفاصيل الحمولة | Content / Remarks")
        self.rem_txt = tk.Text(card, font=self.en_font, width=55, height=3, bd=1, relief="solid")
        self.rem_txt.grid(row=4, column=1, columnspan=3, sticky="w", padx=6, pady=4)

        # Action Buttons
        bf = tk.Frame(P, bg=self.bg_main); bf.pack(pady=15)
        tk.Button(bf, text="💾 حفظ واعتماد الإذن | Save Slip", font=("ae_AlMothnna", 12, "bold"), bg=self.c_suc, fg="white", command=self._save_slip, padx=20, pady=4).pack(side=tk.LEFT, padx=6)
        tk.Button(bf, text="🆕 إذن جديد | New Slip", font=("ae_AlMothnna", 11, "bold"), bg=self.c_pri, fg="white", command=self._reset_slip_form, padx=15, pady=4).pack(side=tk.LEFT, padx=6)

    def _get_next_slip_no(self):
        try:
            conn = sqlite3.connect(DB_MOVEMENT, timeout=5)
            nums = [int(r[0].split("-")[1]) for r in conn.execute("SELECT slip_no FROM dispatch_slips WHERE slip_no LIKE 'DP-%'").fetchall() if r[0].split("-")[1].isdigit()]
            conn.close()
            return f"DP-{max(nums)+1}" if nums else "DP-1001"
        except: return "DP-1001"

    def _reset_slip_form(self):
        for w in (self.slip_ent, self.date_ent, self.co_ref_ent, self.area_ent):
            w.delete(0, tk.END)
        self.slip_ent.insert(0, self._get_next_slip_no())
        self.date_ent.insert(0, datetime.now().strftime("%d-%b-%Y"))
        self.drv_cb.set(""); self.veh_cb.set(""); self.cust_cb.set("")
        self.rem_txt.delete("1.0", tk.END); self.status_var.set("Out for Delivery")
        self.lbl_drv_pic.config(image="", text="صورة\nالسائق")

    def _save_slip(self):
        s_no = self.slip_ent.get().strip()
        drv = self.drv_cb.get().strip()
        cust = self.cust_cb.get().strip()
        if not s_no or not drv or not cust: return messagebox.showwarning("تنبيه", "رقم الإذن، السائق، والعميل حقول إلزامية.")

        data = (
            s_no, format_date_std(self.date_ent.get()), drv, cust,
            self.area_ent.get().strip(), self.co_ref_ent.get().strip(),
            self.veh_cb.get().strip(), self.status_var.get(),
            self.rem_txt.get("1.0", tk.END).strip(),
            self.username, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        try:
            conn = sqlite3.connect(DB_MOVEMENT, timeout=10)
            conn.execute("INSERT OR REPLACE INTO dispatch_slips VALUES (?,?,?,?,?,?,?,?,?,?,?)", data)
            conn.execute("INSERT INTO audit_trail (user, action, timestamp, details) VALUES (?,?,?,?)", (self.username, "إصدار إذن توصيل", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), f"إذن: {s_no} | السائق: {drv}"))
            conn.commit(); conn.close()
            self._reset_slip_form(); self._load_history()
            messagebox.showinfo("نجاح", "تم حفظ وتوثيق إذن التوصيل بنجاح! 🚚")
        except Exception as e: messagebox.showerror("خطأ", str(e))

    def _build_history_tab(self):
        tf = tk.Frame(self.tab_hist, bg=self.bg_main); tf.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        
        # Bar
        bf = tk.Frame(tf, bg=self.bg_main); bf.pack(fill=tk.X, pady=(0, 8))
        for t, c, cmd in [("🖨️ طباعة الإذن | Print Slip", self.c_dark, self._print_slip), ("🗑️ حذف الإذن | Delete", self.c_dan, self._del_slip), ("🔄 تحديث | Refresh", self.c_suc, self._load_history), ("📊 تصدير Excel | Export", "#8e44ad", self._export_excel)]:
            tk.Button(bf, text=t, font=self.ar_bold, bg=c, fg="white", relief="flat", command=cmd, padx=10).pack(side=tk.LEFT, padx=4)

        sf = tk.Frame(bf, bg=self.bg_main); sf.pack(side=tk.RIGHT)
        tk.Label(sf, text="🔍 بحث شامل:", font=self.lbl_font, bg=self.bg_main).pack(side=tk.RIGHT, padx=4)
        self.srch_var = tk.StringVar(); self.srch_var.trace_add("write", lambda *a: self._load_history(self.srch_var.get().strip()))
        ttk.Entry(sf, textvariable=self.srch_var, font=self.en_font, width=30).pack(side=tk.RIGHT)

        # Tree
        sy = ttk.Scrollbar(tf, orient=tk.VERTICAL); sy.pack(side=tk.RIGHT, fill=tk.Y)
        cols = ("Slip No", "Date", "Driver Name", "Customer Name", "Area", "Vehicle", "Status", "COO Ref")
        self.tree = ttk.Treeview(tf, columns=cols, show="headings", yscrollcommand=sy.set, height=18); sy.config(command=self.tree.yview)
        for c, w in [("Slip No",90), ("Date",90), ("Driver Name",180), ("Customer Name",220), ("Area",120), ("Vehicle",110), ("Status",110), ("COO Ref",100)]:
            self.tree.heading(c, text=c); self.tree.column(c, anchor="center" if c not in ("Driver Name", "Customer Name") else "w", width=w)
        
        self.tree.tag_configure("Delivered", background="#d4edda", foreground="#155724")
        self.tree.tag_configure("Cancelled", background="#f8d7da", foreground="#721c24")
        self.tree.pack(fill=tk.BOTH, expand=True)
        self._load_history()

    def _load_history(self, q=""):
        for i in self.tree.get_children(): self.tree.delete(i)
        pq = f"%{q}%"
        try:
            conn = sqlite3.connect(DB_MOVEMENT, timeout=5)
            query = "SELECT slip_no, slip_date, driver_name, customer_name, destination_area, vehicle_number, status, co_reference FROM dispatch_slips WHERE slip_no LIKE ? OR driver_name LIKE ? OR customer_name LIKE ? OR destination_area LIKE ? ORDER BY slip_no DESC"
            for r in conn.execute(query, (pq, pq, pq, pq)).fetchall():
                st = str(r[6]).strip()
                self.tree.insert("", "end", values=r, tags=(st,))
            conn.close()
        except: pass

    def _print_slip(self):
        s = self.tree.selection()
        if not s: return messagebox.showwarning("تنبيه", "حدد إذن توصيل لطباعته.")
        slip_no = self.tree.item(s[0], "values")[0]

        try:
            conn = sqlite3.connect(DB_MOVEMENT, timeout=5)
            r = conn.execute("SELECT * FROM dispatch_slips WHERE slip_no=?", (slip_no,)).fetchone()
            conn.close()
            if not r: return
            
            # r[0]=no, r[1]=date, r[2]=driver, r[3]=cust, r[4]=area, r[5]=co_ref, r[6]=veh, r[7]=status, r[8]=rem
            drv_name = str(r[2]).split(" - ")[1] if " - " in str(r[2]) else str(r[2])
            drv_id = str(r[2]).split(" - ")[0] if " - " in str(r[2]) else ""
            p_drv = self._find_pic(drv_id) if drv_id else ""

            html = f"""<html><head><meta charset="utf-8"><title>Gate Pass - {r[0]}</title>
            <style>
            @page {{ size: A5 landscape; margin: 8mm; }}
            body {{ font-family: Arial, sans-serif; font-size: 12px; color: #333; }}
            .logo-box {{ text-align: center; margin-bottom: 10px; }}
            .logo-box img {{ max-height: 90px; width: 100%; object-fit: contain; }}
            h2 {{ text-align: center; margin: 4px 0 15px 0; font-size: 16px; text-decoration: underline; }}
            table.info {{ width: 100%; border-collapse: collapse; margin-bottom: 15px; }}
            table.info td {{ border: 1px solid #000; padding: 6px 10px; font-size: 12px; }}
            .lbl {{ font-weight: bold; background-color: #eaeded; width: 18%; }}
            .val {{ width: 32%; }}
            .cargo-box {{ border: 1px solid #000; padding: 10px; min-height: 60px; margin-bottom: 25px; }}
            table.sigs {{ width: 100%; text-align: center; margin-top: 30px; font-weight: bold; }}
            table.sigs td {{ width: 33%; border: none; }}
            </style></head><body onload="window.print()">
            <div class="logo-box">{f'<img src="file:///{LOGO_UP_PATH.replace(chr(92), "/")}">'}</div>
            <h2>GATE PASS & DELIVERY SLIP / إذن خروج وتوصيل بضاعة</h2>
            <table class="info">
               <tr><td class="lbl">SLIP NO</td><td class="val"><b>{r[0]}</b></td><td class="lbl">DATE</td><td class="val">{r[1]}</td></tr>
               <tr><td class="lbl">DRIVER NAME</td><td class="val"><b>{drv_name}</b></td><td class="lbl">VEHICLE NO</td><td class="val">{r[6]}</td></tr>
               <tr><td class="lbl">CUSTOMER</td><td colspan="3" style="font-weight:bold; font-size:13px;">{r[3]}</td></tr>
               <tr><td class="lbl">DESTINATION</td><td class="val"><b>{r[4]}</b></td><td class="lbl">COO REF NO</td><td class="val">{r[5]}</td></tr>
            </table>
            <div class="cargo-box">
               <b>CARGO DETAILS / REMARKS (تفاصيل الحمولة):</b><br><br>
               <span style="white-space:pre-wrap; font-size:13px;">{r[8]}</span>
            </div>
            <table class="sigs">
               <tr><td>Storekeeper (أمين المستودع)<br><br>___________________</td><td>Driver (توقيع السائق)<br><br>___________________</td><td>Receiver Stamp & Sig (المستلم)<br><br>___________________</td></tr>
            </table>
            </body></html>"""

            tp = os.path.join(BASE_DIR, "temp_gate_pass.html")
            with open(tp, "w", encoding="utf-8") as f: f.write(html)
            webbrowser.open("file:///" + tp.replace("\\", "/"))
        except Exception as e: messagebox.showerror("خطأ", str(e))

    def _del_slip(self):
        s = self.tree.selection()
        if not s: return messagebox.showwarning("تنبيه", "حدد إذناً للحذف.")
        s_no = self.tree.item(s[0], "values")[0]
        if messagebox.askyesno("تأكيد", f"حذف الإذن {s_no} نهائياً؟"):
            try:
                conn = sqlite3.connect(DB_MOVEMENT, timeout=5)
                conn.execute("DELETE FROM dispatch_slips WHERE slip_no=?", (s_no,))
                conn.execute("INSERT INTO audit_trail (user,action,timestamp,details) VALUES (?,?,?,?)", (self.username, "حذف إذن توصيل", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), s_no))
                conn.commit(); conn.close(); self._load_history()
            except Exception as e: messagebox.showerror("خطأ", str(e))

    def _export_excel(self):
        try:
            conn = sqlite3.connect(DB_MOVEMENT, timeout=5)
            df = pd.read_sql_query("SELECT * FROM dispatch_slips", conn)
            conn.close()
            fp = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
            if fp:
                df.to_excel(fp, index=False)
                messagebox.showinfo("نجاح", "تم تصدير سجل حركة السائقين بنجاح.")
        except Exception as e: messagebox.showerror("خطأ", str(e))

    def _auto_backup(self):
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            dst = os.path.join(BACKUP_DIR, f"drivers_movement_{today}.db")
            if not os.path.exists(dst): shutil.copyfile(DB_MOVEMENT, dst)
        except: pass

if __name__ == "__main__":
    root = tk.Tk(); app = LoginWindow(root); root.mainloop()
