"""
نظام حركة السائقين — Streamlit Cloud Edition
جميع البيانات مخزنة في Google Sheets — بدون SQLite
- لوحة شرف | إدخال حركات | تعديل/حذف بصلاحيات
- إدارة سيارات ومواقع مشتركة لجميع الموظفين
- متعدد المستخدمين في نفس الوقت
"""

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta, time as dt_time
from collections import Counter

# ══════════════════════════════════════════
# إعدادات الصفحة
# ══════════════════════════════════════════
st.set_page_config(page_title="حركة السائقين | Al Hamad", page_icon="🚛", layout="wide")
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
html,body,[class*="css"],.stApp,.stSelectbox,.stTextInput,.stDateInput,
.stTimeInput,.stMarkdown,.stButton,.stForm,.stExpander,.stTabs,
div,span,p,label,input,select,textarea,option,
h1,h2,h3,h4,h5,h6{font-family:'Tahoma','Tajawal',sans-serif!important}
h1,h2,h3{color:#f1c40f!important;text-align:center}
label{font-size:14px!important;color:#95a5a6!important;font-weight:bold}
.stButton>button{background:#2980b9;color:#fff;border-radius:5px;width:100%;
font-weight:bold;border:none}
.stButton>button:hover{background:#3498db;border:1px solid #f1c40f}
input[type="text"],.stTextInput input{text-transform:uppercase!important}
</style>""", unsafe_allow_html=True)

# ══════════════════════════════════════════
# اتصال Google Sheets
# ══════════════════════════════════════════
SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]

@st.cache_resource(ttl=500)
def get_spreadsheet():
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(
            dict(st.secrets["gcp_service_account"]), scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    return gspread.authorize(creds).open("Drivers_Report")

def ensure_worksheets():
    if st.session_state.get('_ws_ok'):
        return
    try:
        ss = get_spreadsheet()
        existing = [w.title for w in ss.worksheets()]
        tabs = {
            "users":        ["username", "password", "role", "display_name"],
            "drivers":      ["name"],
            "customers":    ["name"],
            "cars":         ["car_no"],
            "destinations": ["destination"],
        }
        for name, hdr in tabs.items():
            if name not in existing:
                ws = ss.add_worksheet(title=name, rows=300, cols=len(hdr))
                ws.append_row(hdr)
                if name == "users":
                    ws.append_row(["admin", "admin123", "admin", "المدير"])
        st.session_state['_ws_ok'] = True
    except Exception as e:
        st.error(f"⚠️ خطأ تهيئة: {e}")

# ══════════════════════════════════════════
# قراءة البيانات
# ══════════════════════════════════════════
@st.cache_data(ttl=25)
def read_tab(name):
    try:
        return get_spreadsheet().worksheet(name).get_all_values()
    except:
        return []

def get_users_data():
    d = read_tab("users"); return d[1:] if len(d) > 1 else []

def get_drivers_list():
    d = read_tab("drivers")
    return [""] + sorted({r[0].strip().upper() for r in d[1:] if r and r[0].strip()})

def get_customers_list():
    d = read_tab("customers")
    return [""] + sorted({r[0].strip() for r in d[1:] if r and r[0].strip()})

def get_cars_list():
    d = read_tab("cars")
    return sorted({r[0].strip().upper() for r in d[1:] if r and r[0].strip()})

def get_dest_list():
    d = read_tab("destinations")
    return sorted({r[0].strip().upper() for r in d[1:] if r and r[0].strip()})

def get_display_name(uid):
    uid = str(uid).strip()
    if not uid: return ""
    for r in get_users_data():
        if len(r) >= 4 and str(r[0]).strip() == uid:
            return r[3]
    return uid

def normalize_creator(raw):
    raw = str(raw).strip()
    if not raw: return ""
    for r in get_users_data():
        if len(r) >= 1 and str(r[0]).strip() == raw: return raw
        if len(r) >= 4 and str(r[3]).strip() == raw: return str(r[0]).strip()
    return raw

# ══════════════════════════════════════════
# كتابة البيانات
# ══════════════════════════════════════════
def sheet_append(tab, vals):
    get_spreadsheet().worksheet(tab).append_row(vals)
    st.cache_data.clear()

def sheet_remove(tab, val, col=0):
    ws = get_spreadsheet().worksheet(tab)
    data = ws.get_all_values()
    for i in range(len(data)-1, 0, -1):
        if len(data[i]) > col and data[i][col].strip().upper() == val.strip().upper():
            ws.delete_rows(i+1); break
    st.cache_data.clear()

def sheet_update_cell(tab, old, new, col=0):
    ws = get_spreadsheet().worksheet(tab)
    data = ws.get_all_values()
    for i in range(1, len(data)):
        if len(data[i]) > col and data[i][col].strip().upper() == old.strip().upper():
            ws.update_cell(i+1, col+1, new); break
    st.cache_data.clear()

# ══════════════════════════════════════════
# الوقت 12 ساعة
# ══════════════════════════════════════════
@st.cache_data
def build_time_slots():
    s, m = [], {}
    for t in range(0, 24*60, 5):
        h24, mn = t//60, t%60
        p = "AM" if h24 < 12 else "PM"
        h12 = h24 % 12 or 12
        l = f"{h12:02d}:{mn:02d} {p}"
        s.append(l); m[l] = dt_time(h24, mn)
    return s, m

TIME_SLOTS, TIME_MAP = build_time_slots()

def default_time_idx():
    n = datetime.now(); m5 = (n.minute//5)*5
    h = n.hour; p = "AM" if h < 12 else "PM"; h12 = h%12 or 12
    l = f"{h12:02d}:{m5:02d} {p}"
    return TIME_SLOTS.index(l) if l in TIME_SLOTS else 0

def trip_dur(tf, tt):
    t1 = datetime.combine(datetime.today(), tf)
    t2 = datetime.combine(datetime.today(), tt)
    if t2 < t1: t2 += timedelta(days=1)
    d = t2-t1; return f"{d.seconds//3600:02d}:{(d.seconds//60)%60:02d}"

# ══════════════════════════════════════════
# الجلسة وتسجيل الدخول
# ══════════════════════════════════════════
for k, v in {'logged_in':False, 'username':'', 'real_name':'',
             'do_logout':False, 'user_role':'user'}.items():
    if k not in st.session_state: st.session_state[k] = v

def verify_login(u, p):
    for r in get_users_data():
        if len(r) >= 3 and str(r[0]).strip() == u and str(r[1]).strip() == p:
            role = str(r[2]).strip() if len(r) > 2 else "user"
            disp = str(r[3]).strip() if len(r) > 3 else u
            st.session_state.update({
                'logged_in':True, 'username':u,
                'real_name':disp, 'user_role':role})
            return True
    st.error("❌ بيانات الدخول غير صحيحة"); return False

def log_audit(act, det):
    try:
        ss = get_spreadsheet()
        try:    ws = ss.worksheet("audit")
        except: ws = ss.add_worksheet("audit", 2000, 4); ws.append_row(["user","action","timestamp","details"])
        ws.append_row([st.session_state['username'], act,
                       datetime.now().strftime("%Y-%m-%d %H:%M:%S"), det])
    except: pass

if st.session_state.get('do_logout'):
    for k, v in {'logged_in':False,'username':'','real_name':'',
                 'do_logout':False,'user_role':'user'}.items():
        st.session_state[k] = v
    st.rerun()

# ══════════════════════════════════════════
# تهيئة التبويبات
# ══════════════════════════════════════════
ensure_worksheets()

# ══════════════════════════════════════════
# شاشة الدخول
# ══════════════════════════════════════════
if not st.session_state['logged_in']:
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("<h1 style='color:#f1c40f'>🚛 نظام حركة السائقين</h1>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align:center;color:#95a5a6'>DRIVER MOVEMENT SYSTEM</h4>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align:center;color:#7f8c8d'>Al Hamad Aluminum</h4>", unsafe_allow_html=True)
    st.markdown("---")
    _, c2, _ = st.columns([1, 2, 1])
    with c2:
        st.markdown("<h3 style='color:white;text-align:center'>تسجيل الدخول | LOGIN 🔐</h3>", unsafe_allow_html=True)
        with st.form("login"):
            ui = st.text_input("الرقم الوظيفي | EMPLOYEE ID")
            pi = st.text_input("كلمة المرور | PASSWORD", type="password")
            if st.form_submit_button("دخول | LOGIN"):
                if ui and pi:
                    if verify_login(ui.strip(), pi.strip()): st.rerun()
                else: st.warning("يرجى إدخال جميع البيانات.")
    st.stop()

# ══════════════════════════════════════════
# الواجهة الرئيسية
# ══════════════════════════════════════════
IS_ADMIN = st.session_state['user_role'] == 'admin'
MY_ID    = st.session_state['username']
MY_NAME  = st.session_state['real_name']

# ── الشريط الجانبي ──
with st.sidebar:
    st.markdown("<h2 style='color:#f1c40f'>الملف الشخصي</h2>", unsafe_allow_html=True)
    st.markdown("<div style='text-align:center;font-size:60px'>👤</div>", unsafe_allow_html=True)
    st.markdown(f"### أهلاً بك | WELCOME\n**{MY_NAME}**")
    st.markdown("---")
    if st.button("🔒 تسجيل خروج | LOGOUT"):
        st.session_state['do_logout'] = True; st.rerun()
    st.markdown("---")

    # ── سيارات ──
    st.markdown("<h3 style='color:#f1c40f'>🚗 أرقام السيارات</h3>", unsafe_allow_html=True)
    cars = get_cars_list()
    tc1, tc2 = st.tabs(["➕ إضافة", "✏️ تعديل/حذف"])
    with tc1:
        nc = st.text_input("رقم السيارة:", key="nc", placeholder="مثال: 2770")
        if st.button("✅ إضافة", key="ac"):
            v = nc.strip().upper()
            if v:
                if v not in cars:
                    sheet_append("cars", [v]); st.rerun()
                else: st.warning("موجود!")
    with tc2:
        if cars:
            sc = st.selectbox("اختر:", [""]+cars, key="sc")
            if sc:
                ev = st.text_input("الجديد:", value=sc, key="ev")
                a, b = st.columns(2)
                with a:
                    if st.button("💾", key="s1"):
                        nv = ev.strip().upper()
                        if nv and nv != sc:
                            sheet_update_cell("cars", sc, nv); st.rerun()
                with b:
                    if st.button("🗑️", key="d1"):
                        sheet_remove("cars", sc); st.rerun()
    st.markdown("---")

    # ── مواقع ──
    st.markdown("<h3 style='color:#f1c40f'>📍 المواقع</h3>", unsafe_allow_html=True)
    dests = get_dest_list()
    td1, td2 = st.tabs(["➕ إضافة", "✏️ تعديل/حذف"])
    with td1:
        nd = st.text_input("الموقع:", key="nd", placeholder="مثال: DUBAI")
        if st.button("✅ إضافة", key="ad"):
            v = nd.strip().upper()
            if v:
                if v not in dests:
                    sheet_append("destinations", [v]); st.rerun()
                else: st.warning("موجود!")
    with td2:
        if dests:
            sd = st.selectbox("اختر:", [""]+dests, key="sd")
            if sd:
                dv = st.text_input("الجديد:", value=sd, key="dv")
                a, b = st.columns(2)
                with a:
                    if st.button("💾", key="s2"):
                        nv = dv.strip().upper()
                        if nv and nv != sd:
                            sheet_update_cell("destinations", sd, nv); st.rerun()
                with b:
                    if st.button("🗑️", key="d2"):
                        sheet_remove("destinations", sd); st.rerun()

# ══════════════════════════════════════════
# تحميل بيانات الحركات
# ══════════════════════════════════════════
try:
    ss_obj = get_spreadsheet()
    mv_sheet = ss_obj.sheet1
    sheet_data = mv_sheet.get_all_values()
    CONNECTED = True
except Exception as e:
    CONNECTED = False; sheet_data = []
    st.error(f"⚠️ خطأ اتصال: {e}")

HROWS = 1
if len(sheet_data) >= 2:
    r2 = sheet_data[1]
    if any(kw in str(c).upper() for c in r2
           for kw in ["CAR","DATE","CUSTOMER","NAME","DESTINATION"]):
        HROWS = 2
data_rows = sheet_data[HROWS:] if len(sheet_data) > HROWS else []

# إصلاح SR# المكرر
def fix_duplicate_sr(ws, hrows, rows):
    if not rows: return rows
    seen = set(); dup = False
    for r in rows:
        sr = str(r[0]).strip()
        if sr in seen: dup = True; break
        seen.add(sr)
    if dup:
        batch = []
        for i, r in enumerate(rows):
            ns = str(i+1)
            if str(r[0]).strip() != ns:
                batch.append({'range': f'A{hrows+1+i}', 'values': [[ns]]})
                r[0] = ns
        if batch:
            try: ws.batch_update(batch)
            except: pass
    return rows

if CONNECTED and data_rows:
    data_rows = fix_duplicate_sr(mv_sheet, HROWS, data_rows)
next_sr = len(data_rows) + 1

# ══════════════════════════════════════════
# هيكل الأعمدة
# ══════════════════════════════════════════
INT_COLS = ["SR#","NAME","CAR NO","DATE","CUSTOMER","D.O NO",
            "DESTINATION","TIME OUT","TIME IN","TRIP TIME",
            "TRIP NO","NOTES","REPORT NO","CREATED_BY_RAW"]

SHOW_COLS = ["SR#","NAME","CAR NO","DATE","CUSTOMER","D.O NO",
             "DESTINATION","TIME OUT","TIME IN","TRIP TIME",
             "TRIP NO","REPORT NO","NOTES","CREATED BY"]

COL_LBL = {
    "SR#":"SR#", "NAME":"اسم السائق<br>NAME", "CAR NO":"رقم السيارة<br>CAR NO",
    "DATE":"التاريخ<br>DATE", "CUSTOMER":"العميل<br>CUSTOMER",
    "D.O NO":"رقم التوصيل<br>D.O NO", "DESTINATION":"الموقع<br>DESTINATION",
    "TIME OUT":"وقت الخروج<br>TIME OUT", "TIME IN":"وقت الوصول<br>TIME IN",
    "TRIP TIME":"مدة الرحلة<br>TRIP TIME", "TRIP NO":"رقم الرحلة<br>TRIP NO",
    "REPORT NO":"رقم التقرير<br>REPORT NO", "NOTES":"ملاحظات<br>NOTES",
    "CREATED BY":"مُدخل البيانات<br>CREATED BY",
}

# ══════════════════════════════════════════
# التبويبات
# ══════════════════════════════════════════
tab_lb, tab_entry, tab_records = st.tabs([
    "🏆 لوحة الشرف", "🚛 إدخال حركة السائقين", "📋 سجل الحركات"])

# ══════════════════════════════════════════
# TAB 1: لوحة الشرف
# ══════════════════════════════════════════
with tab_lb:
    st.markdown("<h1 style='color:#d35400'>🏆 مسابقة إدخال حركات السائقين 🏆</h1>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align:center;color:#95a5a6'>DATA ENTRY CHALLENGE</h4>", unsafe_allow_html=True)
    st.markdown("---")
    if data_rows:
        now = datetime.now()
        ws_dt = now - timedelta(days=now.weekday())
        ms_dt = now.replace(day=1)
        ys_dt = now.replace(month=1, day=1)

        def count_period(rows, sdt):
            ctr = Counter()
            for row in rows:
                if len(row) < 14: continue
                raw = str(row[13]).strip()
                if not raw or raw.lower() == "admin": continue
                ek = normalize_creator(raw)
                if not ek: continue
                try:
                    ed = datetime.strptime(str(row[3]).strip().upper(), "%d-%b-%Y")
                    if ed.date() < sdt.date(): continue
                except: continue
                ctr[ek] += 1
            return ctr.most_common(5)

        MEDALS = ["🥇","🥈","🥉","🏅","🏅"]
        MCLRS  = ["#f1c40f","#95a5a6","#d35400","#34495e","#34495e"]
        cw, cm, cy = st.columns(3)
        for col, ttl, sdt in [
            (cw,"🥇 بطل الأسبوع\nTHIS WEEK", ws_dt),
            (cm,"🥈 بطل الشهر\nTHIS MONTH", ms_dt),
            (cy,"🥉 بطل السنة\nTHIS YEAR", ys_dt)]:
            with col:
                st.markdown(f"<h3 style='text-align:center;font-size:15px'>{ttl}</h3>", unsafe_allow_html=True)
                rk = count_period(data_rows, sdt)
                if not rk: st.info("لا يوجد إدخالات بعد"); continue
                for i, (eid, cnt) in enumerate(rk):
                    nm = get_display_name(eid)
                    md = MEDALS[i] if i < 5 else "🏅"
                    clr = MCLRS[i] if i < 5 else "#34495e"
                    st.markdown(
                        f"<div style='background:#2c3e50;padding:10px 14px;"
                        f"border-radius:8px;border-left:5px solid {clr};"
                        f"margin-bottom:8px'>"
                        f"<span style='font-size:22px'>{md}</span> "
                        f"<span style='color:#fff;font-size:15px;"
                        f"font-weight:bold'>{nm}</span>"
                        f"<span style='float:left;color:#27ae60;font-size:16px;"
                        f"font-weight:bold'>{cnt} حركة</span></div>",
                        unsafe_allow_html=True)
    else:
        st.info("لا توجد بيانات.")

# ══════════════════════════════════════════
# TAB 2: إدخال الحركات
# ══════════════════════════════════════════
with tab_entry:
    st.title("🚛 إدخال حركة السائقين")
    st.markdown("---")
    if not CONNECTED:
        st.error("⚠️ لا يوجد اتصال بجوجل شيت."); st.stop()

    dt = default_time_idx()
    with st.form("driver_form", clear_on_submit=True):
        st.markdown(f"<div style='text-align:left;color:#3498db;font-weight:bold'>"
                    f"الرقم التسلسلي (SR#): {next_sr}</div>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        with c1: f_driver = st.selectbox("اسم السائق | NAME", get_drivers_list())
        with c2: f_car    = st.selectbox("رقم السيارة | CAR NO", [""]+get_cars_list())
        with c3: f_date   = st.date_input("التاريخ | DATE")
        with c4: f_cust   = st.selectbox("العميل | CUSTOMER", get_customers_list())
        c5, c6, c7, c8 = st.columns(4)
        with c5: f_do   = st.text_input("رقم التوصيل | D.O NO")
        with c6: f_dest = st.selectbox("الموقع | DESTINATION", [""]+get_dest_list())
        with c7: f_tout = st.selectbox("وقت الخروج | TIME OUT", TIME_SLOTS, index=dt)
        with c8: f_tin  = st.selectbox("وقت الوصول | TIME IN", TIME_SLOTS, index=dt)
        c9, c10, c11 = st.columns(3)
        with c9:  f_tripno   = st.text_input("رقم الرحلة | TRIP NO")
        with c10: f_reportno = st.text_input("رقم التقرير | REPORT NO")
        with c11: f_notes    = st.text_input("الملاحظات | NOTES")
        st.markdown("<br>", unsafe_allow_html=True)
        submit = st.form_submit_button("💾 حفظ البيانات وإضافتها للجدول")

    if submit:
        if not f_driver or not f_car:
            st.warning("⚠️ يرجى تعبئة اسم السائق ورقم السيارة على الأقل.")
        else:
            fd = f_date.strftime("%d-%b-%Y").upper()
            tr = trip_dur(TIME_MAP[f_tout], TIME_MAP[f_tin])
            row = [next_sr, f_driver.upper(), f_car.upper(), fd,
                   f_cust.upper() if f_cust else "",
                   f_do.upper() if f_do else "",
                   f_dest.upper() if f_dest else "",
                   f_tout, f_tin, tr,
                   f_tripno.upper() if f_tripno else "",
                   f_notes.upper() if f_notes else "",
                   f_reportno.upper() if f_reportno else "",
                   MY_ID]
            with st.spinner("جاري الحفظ..."):
                try:
                    mv_sheet.append_row(row)
                    st.cache_data.clear()
                    st.success(f"✅ تم الحفظ! مدة الرحلة: {tr}")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ {e}")

# ══════════════════════════════════════════
# TAB 3: سجل الحركات
# ══════════════════════════════════════════
with tab_records:
    st.markdown("### 📋 جدول سجلات السائقين (الأحدث أولاً)")
    if not data_rows:
        st.info("لا توجد بيانات.")
    else:
        mc = len(INT_COLS)
        clean = [(r + [""]*(mc-len(r)))[:mc] for r in data_rows]
        df = pd.DataFrame(clean, columns=INT_COLS)
        df['Sheet_Row'] = range(HROWS+1, HROWS+1+len(clean))
        df['CREATED BY'] = df['CREATED_BY_RAW'].apply(get_display_name)
        ddf = df.iloc[::-1].reset_index(drop=True)

        # ── الجدول ──
        html = ("<div style='overflow-x:auto'><table style='width:100%;"
                "border-collapse:collapse;text-align:center;font-size:12px'>"
                "<thead><tr style='background:#2c3e50;color:#f1c40f'>")
        for c in SHOW_COLS:
            html += f"<th style='padding:8px 4px;border:1px solid #555'>{COL_LBL.get(c,c)}</th>"
        html += "</tr></thead><tbody>"
        for _, rw in ddf.iterrows():
            html += "<tr>"
            for c in SHOW_COLS:
                val = str(rw[c]) if c in rw and rw[c] else ""
                css = "padding:6px 4px;border:1px solid #444;"
                if c == "TRIP TIME" and val: css += "color:#27ae60;font-weight:bold;"
                html += f"<td style='{css}'>{val}</td>"
            html += "</tr>"
        html += "</tbody></table></div>"
        st.markdown(html, unsafe_allow_html=True)

        # ── إدارة السجلات ──
        st.markdown("---")
        with st.expander("⚙️ إدارة السجلات (تعديل / حذف)", expanded=False):
            opts = [f"{r['Sheet_Row']} | SR#{r['SR#']} - {r['NAME']} - {r['DATE']}"
                    for _, r in df.iloc[::-1].iterrows()]
            sel = st.selectbox("اختر السجل:", [""]+opts, key="rs")
            if sel:
                sr_row = int(sel.split(" | ")[0])
                ri = sr_row - HROWS - 1
                curr = df[df['Sheet_Row'] == sr_row].iloc[0]
                cr_raw = str(clean[ri][13]).strip() if 0 <= ri < len(clean) and len(clean[ri]) > 13 else ""
                cr_norm = normalize_creator(cr_raw)
                my_norm = normalize_creator(MY_ID)
                can = IS_ADMIN or (my_norm == cr_norm)
                cr_disp = get_display_name(cr_raw)

                if not can:
                    st.error(f"🚫 لا تملك صلاحية! السجل أدخله: **{cr_disp}**. فقط صاحبه أو الأدمن.")
                else:
                    st.success(f"✅ لديك صلاحية — أنت: **{MY_NAME}**")
                    act = st.radio("الإجراء:", ["تعديل ✏️","حذف 🗑️"], horizontal=True, key="ar")

                    if act == "حذف 🗑️":
                        dr = st.text_input("سبب الحذف (إلزامي):", key="dr")
                        if st.button("🚨 تأكيد الحذف", type="primary"):
                            if not dr.strip(): st.error("⚠️ أدخل السبب!")
                            else:
                                try:
                                    mv_sheet.delete_rows(sr_row)
                                    log_audit("حذف", f"SR:{curr['SR#']}|{dr}")
                                    st.cache_data.clear()
                                    st.success("✅ تم!"); st.rerun()
                                except Exception as e: st.error(f"خطأ: {e}")

                    elif act == "تعديل ✏️":
                        st.markdown("##### تعديل السجل")
                        with st.form("ef"):
                            try:    pd_ = datetime.strptime(curr['DATE'], "%d-%b-%Y").date()
                            except: pd_ = datetime.today().date()
                            drvs = get_drivers_list()
                            custs = get_customers_list()
                            crs = [""]+get_cars_list()
                            dsts = [""]+get_dest_list()
                            e1, e2 = st.columns(2)
                            with e1: ed = st.selectbox("السائق", drvs,
                                        index=drvs.index(curr['NAME']) if curr['NAME'] in drvs else 0)
                            with e2: ec = st.selectbox("السيارة", crs,
                                        index=crs.index(curr['CAR NO']) if curr['CAR NO'] in crs else 0)
                            e3, e4 = st.columns(2)
                            with e3: edt = st.date_input("التاريخ", value=pd_)
                            with e4: ecu = st.selectbox("العميل", custs,
                                        index=custs.index(curr['CUSTOMER']) if curr['CUSTOMER'] in custs else 0)
                            e5, e6 = st.columns(2)
                            with e5: edo = st.text_input("رقم التوصيل", value=curr['D.O NO'])
                            with e6: eds = st.selectbox("الموقع", dsts,
                                        index=dsts.index(curr['DESTINATION']) if curr['DESTINATION'] in dsts else 0)
                            e7, e8 = st.columns(2)
                            ti = TIME_SLOTS.index(curr['TIME OUT']) if curr['TIME OUT'] in TIME_SLOTS else 0
                            to = TIME_SLOTS.index(curr['TIME IN']) if curr['TIME IN'] in TIME_SLOTS else 0
                            with e7: etf = st.selectbox("وقت الخروج", TIME_SLOTS, index=ti)
                            with e8: ett = st.selectbox("وقت الوصول", TIME_SLOTS, index=to)
                            e9, e10, e11 = st.columns(3)
                            with e9:  etn = st.text_input("رقم الرحلة", value=curr['TRIP NO'])
                            with e10: ern = st.text_input("رقم التقرير", value=curr['REPORT NO'])
                            with e11: en  = st.text_input("ملاحظات", value=curr['NOTES'])

                            if st.form_submit_button("💾 حفظ"):
                                etr = trip_dur(TIME_MAP[etf], TIME_MAP[ett])
                                upd = [curr['SR#'], ed.upper(), ec.upper(),
                                       edt.strftime("%d-%b-%Y").upper(),
                                       ecu.upper() if ecu else "",
                                       edo.upper() if edo else "",
                                       eds.upper() if eds else "",
                                       etf, ett, etr,
                                       etn.upper() if etn else "",
                                       en.upper() if en else "",
                                       ern.upper() if ern else "",
                                       cr_raw]
                                try:
                                    try:    mv_sheet.update(range_name=f"A{sr_row}:N{sr_row}", values=[upd])
                                    except: mv_sheet.update(f"A{sr_row}:N{sr_row}", [upd])
                                    log_audit("تعديل", f"SR:{curr['SR#']}")
                                    st.cache_data.clear()
                                    st.success(f"✅ تم! مدة الرحلة: {etr}"); st.rerun()
                                except Exception as e: st.error(f"خطأ: {e}")
