"""
نظام حركة السائقين — النسخة النهائية v2 (النسخة الهجينة الذكية)
- يعمل على كمبيوتر المكتب (SQLite) + يعمل على السحابة (Google Sheets Fallback)
- SR# تسلسلي التلقائي الإصلاح
- رقم الرحلة TRIP NO + رقم التقرير REPORT NO
"""

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import sqlite3, os, json, pandas as pd
from datetime import datetime, timedelta, time as dt_time
from PIL import Image
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
.stButton>button{background:#2980b9;color:#fff;border-radius:5px;width:100%;font-weight:bold;border:none}
.stButton>button:hover{background:#3498db;border:1px solid #f1c40f}
input[type="text"],.stTextInput input{text-transform:uppercase!important}
</style>""", unsafe_allow_html=True)

# ══════════════════════════════════════════
# المسارات
# ══════════════════════════════════════════
USER_HOME = os.path.expanduser("~")
_P1 = os.path.join(USER_HOME,"OneDrive - al hamad aluminum extrusions","22-02-2022","ERP")
_P2 = os.path.join(USER_HOME,"OneDrive - al hamad aluminum extrusions","haitham seddiqi's files - 22-02-2022","ERP")
BASE_DIR = os.getcwd()
for _p in [_P1,_P2, BASE_DIR]:
    if os.path.exists(_p) and os.path.exists(os.path.join(_p,"confirmation_orders.db")):
        BASE_DIR=_p; break

DB_MAIN     = os.path.join(BASE_DIR,"confirmation_orders.db")
HR_DB       = os.path.join(BASE_DIR,"factory_erp.db")
EMP_PIC_DIR = os.path.join(BASE_DIR,"pic")
LOGO_PATH   = os.path.join(BASE_DIR,"logo2.jpg")
CARS_FILE   = os.path.join(BASE_DIR,"car_numbers.json")
DEST_FILE   = os.path.join(BASE_DIR,"destinations.json")

# ══════════════════════════════════════════
# اتصال Google Sheets (معالج السحابة)
# ══════════════════════════════════════════
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

@st.cache_resource(ttl=500)
def get_spreadsheet():
    if "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    return gspread.authorize(creds).open("Drivers_Report")

try:
    ss_obj = get_spreadsheet()
    sheet = ss_obj.sheet1
    sheet_data = sheet.get_all_values()
    CONNECTED = True
except Exception as e:
    CONNECTED = False; sheet_data = []

# تحديد عدد صفوف العناوين
HROWS = 1
if len(sheet_data) >= 2 and any(kw in str(c).upper() for c in sheet_data[1] for kw in ["CAR","DATE","CUSTOMER"]):
    HROWS = 2
data_rows = sheet_data[HROWS:] if len(sheet_data) > HROWS else []

# ══════════════════════════════════════════
# خريطة الموظفين
# ══════════════════════════════════════════
@st.cache_data(ttl=120)
def build_emp_mapping():
    id2name, name2id = {}, {}
    if not os.path.exists(HR_DB): return id2name, name2id
    try:
        c = sqlite3.connect(HR_DB,timeout=5).cursor()
        c.execute("SELECT emp_id,name_ar,name FROM employees")
        for eid,nar,nen in c.fetchall():
            e = str(eid).strip()
            fn = nar if nar else nen
            if fn:
                first = str(fn).split()[0]; full = str(fn).strip()
                id2name[e]=first; name2id[first]=e; name2id[full]=e
    except: pass
    return id2name, name2id

def normalize_creator(raw):
    raw = str(raw).strip()
    i2n, n2i = build_emp_mapping()
    return i2n.get(raw, n2i.get(raw, raw))

def get_display_name(raw):
    raw = str(raw).strip()
    return build_emp_mapping()[0].get(raw, raw)

# ══════════════════════════════════════════
# دوال جلب البيانات (الذكاء المزدوج: SQLite ثم Google)
# ══════════════════════════════════════════
def load_json(fp):
    if os.path.exists(fp):
        try:
            with open(fp,"r",encoding="utf-8") as f: d=json.load(f); return d if isinstance(d,list) else []
        except: pass
    return []

def save_json(fp,d):
    with open(fp,"w",encoding="utf-8") as f: json.dump(d,f,ensure_ascii=False,indent=2)

def get_car_options(): return [""]+sorted(load_json(CARS_FILE))
def get_dest_options(): return [""]+sorted(load_json(DEST_FILE))

@st.cache_data(ttl=60)
def get_customers():
    if os.path.exists(DB_MAIN):
        try:
            c=sqlite3.connect(DB_MAIN).cursor()
            c.execute("SELECT name FROM customers ORDER BY name")
            return [""]+[r[0] for r in c.fetchall()]
        except: pass
    # Fallback: سحب العملاء من جوجل شيت
    try:
        d = ss_obj.worksheet("customers").get_all_values()
        return [""] + sorted({r[0].strip() for r in d[1:] if r and r[0].strip()})
    except: return [""]

@st.cache_data(ttl=60)
def get_drivers():
    if os.path.exists(HR_DB):
        try:
            c=sqlite3.connect(HR_DB).cursor()
            c.execute("PRAGMA table_info(employees)")
            cols=[x[1].lower() for x in c.fetchall()]
            fq="SELECT name_ar,name FROM employees WHERE status NOT LIKE '%كنسل%'"
            for cd in ['designation','department','job_title']:
                if cd in cols: fq+=f" AND ({cd} LIKE '%سائق%' OR {cd} LIKE '%driver%')"; break
            c.execute(fq)
            return [""]+sorted([str(r[1] if r[1] else r[0]).upper() for r in c.fetchall()])
        except: pass
    # Fallback: سحب السائقين من جوجل شيت
    try:
        d = ss_obj.worksheet("drivers").get_all_values()
        return [""] + sorted({r[0].strip().upper() for r in d[1:] if r and r[0].strip()})
    except: return [""]

# ══════════════════════════════════════════
# الوقت
# ══════════════════════════════════════════
@st.cache_data
def build_time_slots():
    s,m=[],{}
    for t in range(0,24*60,5):
        h24,mn=t//60,t%60; p="AM" if h24<12 else "PM"; h12=h24%12 or 12
        l=f"{h12:02d}:{mn:02d} {p}"; s.append(l); m[l]=dt_time(h24,mn)
    return s,m

TIME_SLOTS, TIME_MAP = build_time_slots()

def default_time_idx():
    n=datetime.now(); l=f"{n.hour%12 or 12:02d}:{(n.minute//5)*5:02d} {'AM' if n.hour<12 else 'PM'}"
    return TIME_SLOTS.index(l) if l in TIME_SLOTS else 0

def trip_dur(tf,tt):
    d = datetime.combine(datetime.today(),tt) - datetime.combine(datetime.today(),tf)
    if d.days < 0: d += timedelta(days=1)
    return f"{d.seconds//3600:02d}:{(d.seconds//60)%60:02d}"

# ══════════════════════════════════════════
# تسجيل الدخول الهجين (The Bulletproof Login)
# ══════════════════════════════════════════
for k,v in {'logged_in':False,'username':'','real_name':'','do_logout':False,'user_role':'user'}.items():
    if k not in st.session_state: st.session_state[k]=v

def verify_login(u, p):
    u, p = u.strip(), p.strip()
    
    # 1. محاولة SQLite المحلية
    if os.path.exists(DB_MAIN):
        try:
            c=sqlite3.connect(DB_MAIN,timeout=5).cursor()
            c.execute("SELECT role FROM app_users WHERE username=? AND password=?",(u,p))
            r=c.fetchone()
            if r:
                rn=get_display_name(u)
                st.session_state.update({'logged_in':True,'username':u,'real_name':rn if rn!=u else u,'user_role':r[0]})
                return True
        except: pass

    # 2. الخطة البديلة: قراءة شيت users من Google Sheets
    if CONNECTED:
        try:
            users_data = ss_obj.worksheet("users").get_all_values()
            for r in users_data[1:]:
                if len(r)>=3 and str(r[0]).strip()==u and str(r[1]).strip()==p:
                    st.session_state.update({
                        'logged_in':True, 'username':u,
                        'real_name':str(r[3]).strip() if len(r)>3 else u,
                        'user_role':str(r[2]).strip()
                    })
                    return True
        except: pass

    # 3. مخرج طوارئ آمن (Fallback Admin) لكي لا يُغلق النظام بوجهك أبداً
    if u == "admin" and p == "admin123":
        st.session_state.update({'logged_in':True,'username':'admin','real_name':'المدير (وضع الطوارئ)','user_role':'admin'})
        return True

    st.error("❌ بيانات الدخول غير صحيحة"); return False

def log_audit(act,det):
    if os.path.exists(DB_MAIN):
        try:
            c=sqlite3.connect(DB_MAIN)
            c.cursor().execute("INSERT INTO audit_trail(user,action,timestamp,details) VALUES(?,?,?,?)",
                               (st.session_state['username'],act,datetime.now().strftime("%Y-%m-%d %H:%M:%S"),det))
            c.commit()
        except: pass

if st.session_state.get('do_logout'):
    for k in ['logged_in','username','real_name','do_logout']: st.session_state[k] = False if k=='do_logout' else ''
    st.session_state['user_role']='user'; st.rerun()

# ══════════════════════════════════════════
# شاشة الدخول
# ══════════════════════════════════════════
if not st.session_state['logged_in']:
    st.markdown("<br><br><br>",unsafe_allow_html=True)
    if os.path.exists(LOGO_PATH):
        _,cc,_=st.columns([3,1,3])
        with cc: st.image(LOGO_PATH,width=120)
    st.markdown("<h1 style='color:#f1c40f'>نظام حركة السائقين</h1>",unsafe_allow_html=True)
    st.markdown("<h4 style='text-align:center;color:#95a5a6'>DRIVER MOVEMENT SYSTEM</h4>",unsafe_allow_html=True)
    st.markdown("---")
    _,c2,_=st.columns([1,2,1])
    with c2:
        st.markdown("<h3 style='color:white;text-align:center'>تسجيل الدخول | LOGIN 🔐</h3>",unsafe_allow_html=True)
        with st.form("login"):
            ui=st.text_input("الرقم الوظيفي | EMPLOYEE ID")
            pi=st.text_input("كلمة المرور | PASSWORD",type="password")
            if st.form_submit_button("دخول | LOGIN"):
                if ui and pi:
                    if verify_login(ui,pi): st.rerun()
                else: st.warning("يرجى إدخال جميع البيانات.")
    st.stop()

# ══════════════════════════════════════════
# ★ إصلاح SR# المكرر
# ══════════════════════════════════════════
def fix_duplicate_sr(sheet_obj, header_rows, rows):
    if not rows: return rows
    seen = set(); needs_fix = False
    for r in rows:
        sr = str(r[0]).strip()
        if sr in seen: needs_fix = True; break
        seen.add(sr)

    if needs_fix:
        updates = []
        for i, row in enumerate(rows):
            new_sr = str(i + 1)
            if str(row[0]).strip() != new_sr:
                updates.append({'range': f'A{header_rows + 1 + i}', 'values': [[new_sr]]})
                row[0] = new_sr
        if updates:
            try: sheet_obj.batch_update(updates)
            except: pass
    return rows

if CONNECTED and data_rows:
    data_rows = fix_duplicate_sr(sheet, HROWS, data_rows)

next_sr = len(data_rows) + 1

# ══════════════════════════════════════════
# الواجهة الرئيسية
# ══════════════════════════════════════════
IS_ADMIN = st.session_state['user_role']=='admin'
MY_ID    = st.session_state['username']
MY_NAME  = st.session_state['real_name']

INTERNAL_COLS = ["SR#","NAME","CAR NO","DATE","CUSTOMER","D.O NO",
                 "DESTINATION","TIME OUT","TIME IN","TRIP TIME",
                 "TRIP NO","NOTES","REPORT NO","CREATED_BY_RAW"]

SHOW_COLS = ["SR#","NAME","CAR NO","DATE","CUSTOMER","D.O NO",
             "DESTINATION","TIME OUT","TIME IN","TRIP TIME",
             "TRIP NO","REPORT NO","NOTES","CREATED BY"]

COL_LABELS = {
    "SR#":"SR#", "NAME":"اسم السائق<br>NAME", "CAR NO":"رقم السيارة<br>CAR NO",
    "DATE":"التاريخ<br>DATE", "CUSTOMER":"العميل<br>CUSTOMER",
    "D.O NO":"رقم التوصيل<br>D.O NO", "DESTINATION":"الموقع<br>DESTINATION",
    "TIME OUT":"وقت الخروج<br>TIME OUT", "TIME IN":"وقت الوصول<br>TIME IN",
    "TRIP TIME":"مدة الرحلة<br>TRIP TIME", "TRIP NO":"رقم الرحلة<br>TRIP NO",
    "REPORT NO":"رقم التقرير<br>REPORT NO", "NOTES":"ملاحظات<br>NOTES",
    "CREATED BY":"مُدخل البيانات<br>CREATED BY",
}

with st.sidebar:
    st.markdown("<h2 style='color:#f1c40f'>الملف الشخصي</h2>",unsafe_allow_html=True)
    shown=False
    for ext in [".jpg",".jpeg",".png"]:
        pp=os.path.join(EMP_PIC_DIR,f"{MY_ID}{ext}")
        if os.path.exists(pp):
            try: st.image(Image.open(pp),width=120); shown=True; break
            except: pass
    if not shown: st.markdown("<div style='font-size:60px;text-align:center'>👤</div>",unsafe_allow_html=True)
    st.markdown(f"### أهلاً بك | WELCOME\n**{MY_NAME}**")
    st.markdown("---")
    if st.button("🔒 تسجيل خروج | LOGOUT"): st.session_state['do_logout']=True; st.rerun()
    st.markdown("---")

    st.markdown("<h3 style='color:#f1c40f'>🚗 إدارة أرقام السيارات</h3>",unsafe_allow_html=True)
    cl=load_json(CARS_FILE)
    t1,t2=st.tabs(["➕ إضافة","✏️ تعديل/حذف"])
    with t1:
        nc=st.text_input("رقم السيارة:",key="nc",placeholder="مثال: 2770")
        if st.button("✅ إضافة",key="ac") and nc.strip().upper():
            if nc.strip().upper() not in cl: cl.append(nc.strip().upper()); save_json(CARS_FILE,cl); st.rerun()
            else: st.warning("موجود!")
    with t2:
        if cl:
            sc=st.selectbox("اختر:",[""]+sorted(cl),key="sc")
            if sc:
                ev=st.text_input("الجديد:",value=sc,key="ev")
                a,b=st.columns(2)
                with a:
                    if st.button("💾",key="s1") and ev.strip().upper()!=sc:
                        cl[cl.index(sc)]=ev.strip().upper(); save_json(CARS_FILE,cl); st.rerun()
                with b:
                    if st.button("🗑️",key="d1"): cl.remove(sc); save_json(CARS_FILE,cl); st.rerun()
    st.markdown("---")

    st.markdown("<h3 style='color:#f1c40f'>📍 إدارة المواقع</h3>",unsafe_allow_html=True)
    dl=load_json(DEST_FILE)
    t3,t4=st.tabs(["➕ إضافة","✏️ تعديل/حذف"])
    with t3:
        nd=st.text_input("الموقع:",key="nd",placeholder="مثال: DUBAI")
        if st.button("✅ إضافة",key="ad") and nd.strip().upper():
            if nd.strip().upper() not in dl: dl.append(nd.strip().upper()); save_json(DEST_FILE,dl); st.rerun()
            else: st.warning("موجود!")
    with t4:
        if dl:
            sd=st.selectbox("اختر:",[""]+sorted(dl),key="sd")
            if sd:
                dv=st.text_input("الجديد:",value=sd,key="dv")
                a,b=st.columns(2)
                with a:
                    if st.button("💾",key="s2") and dv.strip().upper()!=sd:
                        dl[dl.index(sd)]=dv.strip().upper(); save_json(DEST_FILE,dl); st.rerun()
                with b:
                    if st.button("🗑️",key="d2"): dl.remove(sd); save_json(DEST_FILE,dl); st.rerun()

tab_lb, tab_entry, tab_records = st.tabs(["🏆 لوحة الشرف", "🚛 إدخال حركة السائقين", "📋 سجل الحركات"])

with tab_lb:
    st.markdown("<h1 style='color:#d35400'>🏆 مسابقة إدخال حركات السائقين 🏆</h1>",unsafe_allow_html=True)
    st.markdown("---")
    if data_rows:
        now=datetime.now()
        ws=now-timedelta(days=now.weekday()); ms=now.replace(day=1); ys=now.replace(month=1,day=1)
        def count_period(rows,sdt):
            ctr=Counter()
            for row in rows:
                if len(row)<14: continue
                raw=str(row[13]).strip()
                if not raw or raw.lower()=="admin": continue
                ek=normalize_creator(raw)
                if not ek: continue
                try:
                    if datetime.strptime(str(row[3]).strip().upper(),"%d-%b-%Y").date() >= sdt.date(): ctr[ek]+=1
                except: continue
            return ctr.most_common(5)
        MEDALS, MCLRS = ["🥇","🥈","🥉","🏅","🏅"], ["#f1c40f","#95a5a6","#d35400","#34495e","#34495e"]
        cw,cm,cy=st.columns(3)
        for col,ttl,sdt in [(cw,"🥇 بطل الأسبوع\nTHIS WEEK",ws),(cm,"🥈 بطل الشهر\nTHIS MONTH",ms),(cy,"🥉 بطل السنة\nTHIS YEAR",ys)]:
            with col:
                st.markdown(f"<h3 style='text-align:center;font-size:15px'>{ttl}</h3>",unsafe_allow_html=True)
                rk=count_period(data_rows,sdt)
                if not rk: st.info("لا يوجد إدخالات بعد"); continue
                for i,(eid,cnt) in enumerate(rk):
                    st.markdown(f"<div style='background:#2c3e50;padding:8px 12px;border-radius:8px;border-left:4px solid {MCLRS[i]};margin-bottom:6px'><span style='font-size:20px'>{MEDALS[i]}</span> <span style='color:#fff;font-size:15px;font-weight:bold'>{get_display_name(eid)}</span><span style='float:left;color:#27ae60;font-size:15px;font-weight:bold'>{cnt} حركة</span></div>",unsafe_allow_html=True)
    else: st.info("لا توجد بيانات.")

with tab_entry:
    st.title("🚛 إدخال حركة السائقين")
    st.markdown("---")
    if not CONNECTED: st.error("⚠️ لا يوجد اتصال بجوجل شيت."); st.stop()
    dt_idx = default_time_idx()
    with st.form("driver_form",clear_on_submit=True):
        st.markdown(f"<div style='text-align:left;color:#3498db;font-weight:bold'>الرقم التسلسلي (SR#): {next_sr}</div>",unsafe_allow_html=True)
        c1,c2,c3,c4=st.columns(4)
        with c1: f_driver=st.selectbox("اسم السائق | NAME", get_drivers())
        with c2: f_car=st.selectbox("رقم السيارة | CAR NO", get_car_options())
        with c3: f_date=st.date_input("التاريخ | DATE")
        with c4: f_cust=st.selectbox("العميل | CUSTOMER", get_customers())
        c5,c6,c7,c8=st.columns(4)
        with c5: f_do=st.text_input("رقم التوصيل | D.O NO")
        with c6: f_dest=st.selectbox("الموقع | DESTINATION", get_dest_options())
        with c7: f_tout=st.selectbox("وقت الخروج | TIME OUT",TIME_SLOTS,index=dt_idx)
        with c8: f_tin=st.selectbox("وقت الوصول | TIME IN",TIME_SLOTS,index=dt_idx)
        c9,c10,c11=st.columns(3)
        with c9:  f_tripno=st.text_input("رقم الرحلة | TRIP NO")
        with c10: f_reportno=st.text_input("رقم التقرير | REPORT NO")
        with c11: f_notes=st.text_input("الملاحظات | NOTES")
        submit=st.form_submit_button("💾 حفظ البيانات وإضافتها للجدول")

    if submit:
        if not f_driver or not f_car: st.warning("⚠️ يرجى تعبئة اسم السائق ورقم السيارة على الأقل.")
        else:
            tr = trip_dur(TIME_MAP[f_tout],TIME_MAP[f_tin])
            row = [next_sr, f_driver.upper(), f_car.upper(), f_date.strftime("%d-%b-%Y").upper(),
                   f_cust.upper() if f_cust else "", f_do.upper() if f_do else "",
                   f_dest.upper() if f_dest else "", f_tout, f_tin, tr,
                   f_tripno.upper() if f_tripno else "", f_notes.upper() if f_notes else "",
                   f_reportno.upper() if f_reportno else "", MY_ID]
            with st.spinner("جاري الحفظ..."):
                try: sheet.append_row(row); st.success(f"✅ تم الحفظ! مدة الرحلة: {tr}"); st.rerun()
                except Exception as e: st.error(f"❌ {e}")

with tab_records:
    st.markdown("### 📋 جدول سجلات السائقين")
    if not data_rows: st.info("لا توجد بيانات.")
    else:
        mc = len(INTERNAL_COLS)
        clean = [(r + [""]*(mc-len(r)))[:mc] for r in data_rows]
        df = pd.DataFrame(clean, columns=INTERNAL_COLS)
        df['Sheet_Row'] = range(HROWS+1, HROWS+1+len(clean))
        df['CREATED BY'] = df['CREATED_BY_RAW'].apply(get_display_name)
        
        html="<div style='overflow-x:auto'><table style='width:100%;border-collapse:collapse;text-align:center;font-size:12px'><thead><tr style='background:#2c3e50;color:#f1c40f'>"
        for c in SHOW_COLS: html+=f"<th style='padding:8px 4px;border:1px solid #555'>{COL_LABELS.get(c,c)}</th>"
        html+="</tr></thead><tbody>"
        for _,r in df.iloc[::-1].iterrows():
            html+="<tr>"
            for c in SHOW_COLS:
                val = str(r[c]) if c in r and r[c] else ""
                css = "padding:6px 4px;border:1px solid #444;" + ("color:#27ae60;font-weight:bold;" if c=="TRIP TIME" and val else "")
                html+=f"<td style='{css}'>{val}</td>"
            html+="</tr>"
        html+="</tbody></table></div>"
        st.markdown(html,unsafe_allow_html=True)

        st.markdown("---")
        with st.expander("⚙️ إدارة السجلات (تعديل / حذف)",expanded=False):
            opts = [f"{r['Sheet_Row']} | SR#{r['SR#']} - {r['NAME']} - {r['DATE']}" for _, r in df.iloc[::-1].iterrows()]
            sel = st.selectbox("اختر السجل:",[""]+opts,key="rs")
            if sel:
                sr_row = int(sel.split(" | ")[0])
                curr = df[df['Sheet_Row']==sr_row].iloc[0]
                cr_raw = str(clean[sr_row-HROWS-1][13]).strip() if 0<=(sr_row-HROWS-1)<len(clean) else ""
                if not (IS_ADMIN or normalize_creator(MY_ID)==normalize_creator(cr_raw)):
                    st.error(f"🚫 لا تملك صلاحية! السجل أدخله: **{get_display_name(cr_raw)}**.")
                else:
                    act = st.radio("الإجراء:",["تعديل ✏️","حذف 🗑️"],horizontal=True,key="ar")
                    if act=="حذف 🗑️":
                        dr=st.text_input("سبب الحذف (إلزامي):")
                        if st.button("🚨 تأكيد الحذف",type="primary") and dr.strip():
                            sheet.delete_rows(sr_row); log_audit("حذف",f"SR:{curr['SR#']}|{dr}"); st.rerun()
                    elif act=="تعديل ✏️":
                        with st.form("ef"):
                            try: pd_=datetime.strptime(curr['DATE'],"%d-%b-%Y").date()
                            except: pd_=datetime.today().date()
                            do, co, cao, dso = get_drivers(), get_customers(), get_car_options(), get_dest_options()
                            e1,e2=st.columns(2)
                            with e1: ed=st.selectbox("السائق",do,index=do.index(curr['NAME']) if curr['NAME'] in do else 0)
                            with e2: ec=st.selectbox("السيارة",cao,index=cao.index(curr['CAR NO']) if curr['CAR NO'] in cao else 0)
                            e3,e4=st.columns(2)
                            with e3: edt=st.date_input("التاريخ",value=pd_)
                            with e4: ecu=st.selectbox("العميل",co,index=co.index(curr['CUSTOMER']) if curr['CUSTOMER'] in co else 0)
                            e5,e6=st.columns(2)
                            with e5: edo=st.text_input("رقم التوصيل",value=curr['D.O NO'])
                            with e6: eds=st.selectbox("الموقع",dso,index=dso.index(curr['DESTINATION']) if curr['DESTINATION'] in dso else 0)
                            e7,e8=st.columns(2)
                            with e7: etf=st.selectbox("وقت الخروج",TIME_SLOTS,index=TIME_SLOTS.index(curr['TIME OUT']) if curr['TIME OUT'] in TIME_SLOTS else 0)
                            with e8: ett=st.selectbox("وقت الوصول",TIME_SLOTS,index=TIME_SLOTS.index(curr['TIME IN']) if curr['TIME IN'] in TIME_SLOTS else 0)
                            e9,e10,e11=st.columns(3)
                            with e9:  etn=st.text_input("رقم الرحلة",value=curr['TRIP NO'])
                            with e10: ern=st.text_input("رقم التقرير",value=curr['REPORT NO'])
                            with e11: en=st.text_input("ملاحظات",value=curr['NOTES'])

                            if st.form_submit_button("💾 حفظ"):
                                etr=trip_dur(TIME_MAP[etf],TIME_MAP[ett])
                                upd=[curr['SR#'], ed.upper(), ec.upper(), edt.strftime("%d-%b-%Y").upper(),
                                     ecu.upper() if ecu else "", edo.upper() if edo else "",
                                     eds.upper() if eds else "", etf, ett, etr,
                                     etn.upper() if etn else "", en.upper() if en else "",
                                     ern.upper() if ern else "", cr_raw]
                                try: sheet.update(f"A{sr_row}:N{sr_row}",[upd]); log_audit("تعديل",f"SR:{curr['SR#']}"); st.rerun()
                                except Exception as e: st.error(f"خطأ: {e}")
