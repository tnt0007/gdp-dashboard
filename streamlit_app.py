"""
نظام حركة السائقين — النسخة النهائية v2
- SR# تسلسلي بدون تكرار (يُصلح البيانات القديمة تلقائياً)
- رقم الرحلة TRIP NO + رقم التقرير REPORT NO
- مربوط بـ confirmation_orders.db + factory_erp.db
- اليوزر = الرقم الوظيفي emp_id
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
# المسارات — نفس نظام CO
# ══════════════════════════════════════════
USER_HOME = os.path.expanduser("~")
_P1 = os.path.join(USER_HOME,"OneDrive - al hamad aluminum extrusions","22-02-2022","ERP")
_P2 = os.path.join(USER_HOME,"OneDrive - al hamad aluminum extrusions","haitham seddiqi's files - 22-02-2022","ERP")
_P3 = os.getcwd()
BASE_DIR = _P3
for _p in [_P1,_P2,_P3]:
    if os.path.exists(_p) and os.path.exists(os.path.join(_p,"confirmation_orders.db")):
        BASE_DIR=_p; break

DB_MAIN     = os.path.join(BASE_DIR,"confirmation_orders.db")
HR_DB       = os.path.join(BASE_DIR,"factory_erp.db")
EMP_PIC_DIR = os.path.join(BASE_DIR,"pic")
LOGO_PATH   = os.path.join(BASE_DIR,"logo2.jpg")
CARS_FILE   = os.path.join(BASE_DIR,"car_numbers.json")
DEST_FILE   = os.path.join(BASE_DIR,"destinations.json")

# ══════════════════════════════════════════
# خريطة الموظفين: رقم ↔ اسم
# ══════════════════════════════════════════
@st.cache_data(ttl=120)
def build_emp_mapping():
    id2name, name2id = {}, {}
    if not os.path.exists(HR_DB): return id2name, name2id
    try:
        c = sqlite3.connect(HR_DB,timeout=5000).cursor()
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
    if not raw: return ""
    i2n, n2i = build_emp_mapping()
    if raw in i2n: return raw
    if raw in n2i: return n2i[raw]
    return raw

def get_display_name(raw):
    raw = str(raw).strip()
    if not raw: return ""
    i2n, n2i = build_emp_mapping()
    if raw in i2n: return i2n[raw]
    return raw

# ══════════════════════════════════════════
# JSON — سيارات + مواقع مشتركة
# ══════════════════════════════════════════
def load_json(fp):
    if os.path.exists(fp):
        try:
            with open(fp,"r",encoding="utf-8") as f:
                d=json.load(f); return d if isinstance(d,list) else []
        except: pass
    return []
def save_json(fp,d):
    with open(fp,"w",encoding="utf-8") as f: json.dump(d,f,ensure_ascii=False,indent=2)
def get_car_options(): return [""]+sorted(load_json(CARS_FILE))
def get_dest_options(): return [""]+sorted(load_json(DEST_FILE))

# ══════════════════════════════════════════
# قواعد البيانات الرئيسية
# ══════════════════════════════════════════
@st.cache_data(ttl=60)
def get_customers():
    try:
        c=sqlite3.connect(DB_MAIN).cursor()
        c.execute("SELECT name FROM customers ORDER BY name")
        return [""]+[r[0] for r in c.fetchall()]
    except: return [""]

@st.cache_data(ttl=60)
def get_drivers():
    try:
        conn=sqlite3.connect(HR_DB); c=conn.cursor()
        c.execute("PRAGMA table_info(employees)")
        cols=[x[1].lower() for x in c.fetchall()]
        fq="SELECT name_ar,name FROM employees WHERE status NOT LIKE '%كنسل%'"
        for cd in ['designation','department','job_title']:
            if cd in cols: fq+=f" AND ({cd} LIKE '%سائق%' OR {cd} LIKE '%driver%')"; break
        c.execute(fq)
        return [""]+sorted([str(r[1] if r[1] else r[0]).upper() for r in c.fetchall()])
    except: return [""]

# ══════════════════════════════════════════
# الوقت 12 ساعة
# ══════════════════════════════════════════
@st.cache_data
def build_time_slots():
    s,m=[],{}
    for t in range(0,24*60,5):
        h24,mn=t//60,t%60; p="AM" if h24<12 else "PM"; h12=h24%12 or 12
        l=f"{h12:02d}:{mn:02d} {p}"; s.append(l); m[l]=dt_time(h24,mn)
    return s,m
TIME_SLOTS,TIME_MAP=build_time_slots()

def default_time_idx():
    n=datetime.now(); m5=(n.minute//5)*5; h=n.hour; p="AM" if h<12 else "PM"; h12=h%12 or 12
    l=f"{h12:02d}:{m5:02d} {p}"
    return TIME_SLOTS.index(l) if l in TIME_SLOTS else 0

def trip_dur(tf,tt):
    t1=datetime.combine(datetime.today(),tf); t2=datetime.combine(datetime.today(),tt)
    if t2<t1: t2+=timedelta(days=1)
    d=t2-t1; return f"{d.seconds//3600:02d}:{(d.seconds//60)%60:02d}"

# ══════════════════════════════════════════
# الجلسة
# ══════════════════════════════════════════
for k,v in {'logged_in':False,'username':'','real_name':'','do_logout':False,'user_role':'user'}.items():
    if k not in st.session_state: st.session_state[k]=v

def verify_login(u,p):
    try:
        c=sqlite3.connect(DB_MAIN,timeout=5000).cursor()
        c.execute("SELECT role FROM app_users WHERE username=? AND password=?",(u,p))
        r=c.fetchone()
        if r:
            rn=get_display_name(u)
            st.session_state.update({'logged_in':True,'username':u,'real_name':rn if rn!=u else u,'user_role':r[0]})
            return True
        st.error("❌ بيانات الدخول غير صحيحة"); return False
    except Exception as e: st.error(f"⚠️ {e}"); return False

def log_audit(act,det):
    try:
        c=sqlite3.connect(DB_MAIN); c.cursor().execute(
            "INSERT INTO audit_trail(user,action,timestamp,details) VALUES(?,?,?,?)",
            (st.session_state['username'],act,datetime.now().strftime("%Y-%m-%d %H:%M:%S"),det))
        c.commit()
    except: pass

if st.session_state.get('do_logout'):
    for k,v in {'logged_in':False,'username':'','real_name':'','do_logout':False,'user_role':'user'}.items():
        st.session_state[k]=v
    st.rerun()

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
                    if verify_login(ui.strip(),pi.strip()): st.rerun()
                else: st.warning("يرجى إدخال جميع البيانات.")
    st.stop()

# ══════════════════════════════════════════
# الواجهة الرئيسية
# ══════════════════════════════════════════
IS_ADMIN = st.session_state['user_role']=='admin'
MY_ID    = st.session_state['username']
MY_NAME  = st.session_state['real_name']

# الشريط الجانبي
with st.sidebar:
    st.markdown("<h2 style='color:#f1c40f'>الملف الشخصي</h2>",unsafe_allow_html=True)
    for ext in [".jpg",".jpeg",".png"]:
        pp=os.path.join(EMP_PIC_DIR,f"{MY_ID}{ext}")
        if os.path.exists(pp):
            try: st.image(Image.open(pp),width=120); break
            except: pass
    st.markdown(f"### أهلاً بك | WELCOME\n**{MY_NAME}**")
    st.markdown("---")
    if st.button("🔒 تسجيل خروج | LOGOUT"):
        st.session_state['do_logout']=True; st.rerun()
    st.markdown("---")

    # سيارات
    st.markdown("<h3 style='color:#f1c40f'>🚗 إدارة أرقام السيارات</h3>",unsafe_allow_html=True)
    cl=load_json(CARS_FILE)
    t1,t2=st.tabs(["➕ إضافة","✏️ تعديل/حذف"])
    with t1:
        nc=st.text_input("رقم السيارة:",key="nc",placeholder="مثال: 2770")
        if st.button("✅ إضافة",key="ac"):
            v=nc.strip().upper()
            if v:
                if v not in cl: cl.append(v); save_json(CARS_FILE,cl); st.rerun()
                else: st.warning("موجود!")
    with t2:
        if cl:
            sc=st.selectbox("اختر:",[""]+sorted(cl),key="sc")
            if sc:
                ev=st.text_input("الجديد:",value=sc,key="ev")
                a,b=st.columns(2)
                with a:
                    if st.button("💾",key="s1"):
                        nv=ev.strip().upper()
                        if nv and nv!=sc: cl[cl.index(sc)]=nv; save_json(CARS_FILE,cl); st.rerun()
                with b:
                    if st.button("🗑️",key="d1"): cl.remove(sc); save_json(CARS_FILE,cl); st.rerun()
    st.markdown("---")

    # مواقع
    st.markdown("<h3 style='color:#f1c40f'>📍 إدارة المواقع</h3>",unsafe_allow_html=True)
    dl=load_json(DEST_FILE)
    t3,t4=st.tabs(["➕ إضافة","✏️ تعديل/حذف"])
    with t3:
        nd=st.text_input("الموقع:",key="nd",placeholder="مثال: DUBAI")
        if st.button("✅ إضافة",key="ad"):
            v=nd.strip().upper()
            if v:
                if v not in dl: dl.append(v); save_json(DEST_FILE,dl); st.rerun()
                else: st.warning("موجود!")
    with t4:
        if dl:
            sd=st.selectbox("اختر:",[""]+sorted(dl),key="sd")
            if sd:
                dv=st.text_input("الجديد:",value=sd,key="dv")
                a,b=st.columns(2)
                with a:
                    if st.button("💾",key="s2"):
                        nv=dv.strip().upper()
                        if nv and nv!=sd: dl[dl.index(sd)]=nv; save_json(DEST_FILE,dl); st.rerun()
                with b:
                    if st.button("🗑️",key="d2"): dl.remove(sd); save_json(DEST_FILE,dl); st.rerun()

# ══════════════════════════════════════════
# جوجل شيت
# ══════════════════════════════════════════
SCOPES=["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]
try:
    creds=Credentials.from_service_account_file("credentials.json",scopes=SCOPES)
    sheet=gspread.authorize(creds).open("Drivers_Report").sheet1
    sheet_data=sheet.get_all_values(); CONNECTED=True
except: CONNECTED=False; sheet_data=[]

# تحديد عدد صفوف العناوين
HROWS=1
if len(sheet_data)>=2:
    r2=sheet_data[1]
    if any(kw in str(c).upper() for c in r2 for kw in ["CAR","DATE","CUSTOMER","NAME","DESTINATION"]):
        HROWS=2
data_rows=sheet_data[HROWS:] if len(sheet_data)>HROWS else []

# ══════════════════════════════════════════
# ★ إصلاح SR# المكرر — إعادة ترقيم تلقائي
# ══════════════════════════════════════════
def fix_duplicate_sr(sheet_obj, header_rows, rows):
    """فحص وإصلاح الأرقام التسلسلية المكررة"""
    if not rows:
        return rows
    needs_fix = False
    seen = set()
    for row in rows:
        sr = str(row[0]).strip()
        if sr in seen:
            needs_fix = True; break
        seen.add(sr)

    if needs_fix:
        # إعادة ترقيم تسلسلي: 1, 2, 3, ...
        updates = []
        for i, row in enumerate(rows):
            new_sr = str(i + 1)
            if str(row[0]).strip() != new_sr:
                row_num = header_rows + 1 + i
                updates.append({'range': f'A{row_num}', 'values': [[new_sr]]})
                row[0] = new_sr
        if updates:
            try:
                sheet_obj.batch_update(updates)
            except:
                pass
    return rows

if CONNECTED and data_rows:
    data_rows = fix_duplicate_sr(sheet, HROWS, data_rows)

next_sr = len(data_rows) + 1

# ══════════════════════════════════════════
# هيكل الأعمدة (14 عمود A-N)
# ══════════════════════════════════════════
# 0:SR# 1:NAME 2:CAR_NO 3:DATE 4:CUSTOMER 5:DO_NO 6:DESTINATION
# 7:TIME_OUT 8:TIME_IN 9:TRIP_TIME 10:TRIP_NO 11:NOTES 12:REPORT_NO 13:CREATED_BY

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

# ══════════════════════════════════════════
# التبويبات — لوحة الشرف أولاً
# ══════════════════════════════════════════
tab_lb, tab_entry, tab_records = st.tabs([
    "🏆 لوحة الشرف", "🚛 إدخال حركة السائقين", "📋 سجل الحركات"])

# ══════════════════════════════════════════
# TAB 1: لوحة الشرف
# ══════════════════════════════════════════
with tab_lb:
    st.markdown("<h1 style='color:#d35400'>🏆 مسابقة إدخال حركات السائقين 🏆</h1>",unsafe_allow_html=True)
    st.markdown("<h4 style='text-align:center;color:#95a5a6'>DATA ENTRY CHALLENGE</h4>",unsafe_allow_html=True)
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
                    ed=datetime.strptime(str(row[3]).strip().upper(),"%d-%b-%Y")
                    if ed.date()<sdt.date(): continue
                except: continue
                ctr[ek]+=1
            return ctr.most_common(5)
        MEDALS=["🥇","🥈","🥉","🏅","🏅"]
        MCLRS=["#f1c40f","#95a5a6","#d35400","#34495e","#34495e"]
        cw,cm,cy=st.columns(3)
        for col,ttl,sdt in [(cw,"🥇 بطل الأسبوع\nTHIS WEEK",ws),(cm,"🥈 بطل الشهر\nTHIS MONTH",ms),(cy,"🥉 بطل السنة\nTHIS YEAR",ys)]:
            with col:
                st.markdown(f"<h3 style='text-align:center;font-size:15px'>{ttl}</h3>",unsafe_allow_html=True)
                rk=count_period(data_rows,sdt)
                if not rk: st.info("لا يوجد إدخالات بعد"); continue
                for i,(eid,cnt) in enumerate(rk):
                    nm=get_display_name(eid); md=MEDALS[i] if i<5 else "🏅"; clr=MCLRS[i] if i<5 else "#34495e"
                    pc,ic=st.columns([1,3])
                    with pc:
                        shown=False
                        for ext in [".jpg",".jpeg",".png"]:
                            pp=os.path.join(EMP_PIC_DIR,f"{eid}{ext}")
                            if os.path.exists(pp):
                                try: st.image(Image.open(pp),width=50); shown=True; break
                                except: pass
                        if not shown: st.markdown("<div style='font-size:40px;text-align:center'>👤</div>",unsafe_allow_html=True)
                    with ic:
                        st.markdown(f"<div style='background:#2c3e50;padding:8px 12px;border-radius:8px;border-left:4px solid {clr};margin-bottom:6px'><span style='font-size:20px'>{md}</span> <span style='color:#fff;font-size:15px;font-weight:bold'>{nm}</span><br><span style='color:#27ae60;font-size:16px;font-weight:bold'>{cnt} حركة</span></div>",unsafe_allow_html=True)
    else: st.info("لا توجد بيانات.")

# ══════════════════════════════════════════
# TAB 2: إدخال الحركات
# ══════════════════════════════════════════
with tab_entry:
    cl,ct=st.columns([1,4])
    if os.path.exists(LOGO_PATH):
        with cl: st.image(LOGO_PATH,width=60)
    with ct: st.title("🚛 إدخال حركة السائقين")
    st.markdown("---")
    if not CONNECTED: st.error("⚠️ لا يوجد اتصال بجوجل شيت."); st.stop()
    dt=default_time_idx()
    with st.form("driver_form",clear_on_submit=True):
        st.markdown(f"<div style='text-align:left;color:#3498db;font-weight:bold'>الرقم التسلسلي (SR#): {next_sr}</div>",unsafe_allow_html=True)
        c1,c2,c3,c4=st.columns(4)
        with c1: f_driver=st.selectbox("اسم السائق | NAME",get_drivers())
        with c2: f_car=st.selectbox("رقم السيارة | CAR NO",get_car_options())
        with c3: f_date=st.date_input("التاريخ | DATE")
        with c4: f_cust=st.selectbox("العميل | CUSTOMER",get_customers())
        c5,c6,c7,c8=st.columns(4)
        with c5: f_do=st.text_input("رقم التوصيل | D.O NO")
        with c6: f_dest=st.selectbox("الموقع | DESTINATION",get_dest_options())
        with c7: f_tout=st.selectbox("وقت الخروج | TIME OUT",TIME_SLOTS,index=dt)
        with c8: f_tin=st.selectbox("وقت الوصول | TIME IN",TIME_SLOTS,index=dt)
        # ★ الحقول الجديدة
        c9,c10,c11=st.columns(3)
        with c9:  f_tripno=st.text_input("رقم الرحلة | TRIP NO")
        with c10: f_reportno=st.text_input("رقم التقرير | REPORT NO")
        with c11: f_notes=st.text_input("الملاحظات | NOTES")
        st.markdown("<br>",unsafe_allow_html=True)
        submit=st.form_submit_button("💾 حفظ البيانات وإضافتها للجدول")

    if submit:
        if not f_driver or not f_car:
            st.warning("⚠️ يرجى تعبئة اسم السائق ورقم السيارة على الأقل.")
        else:
            fd=f_date.strftime("%d-%b-%Y").upper()
            tr=trip_dur(TIME_MAP[f_tout],TIME_MAP[f_tin])
            row=[
                next_sr,                                        # 0: SR#
                f_driver.upper(),                               # 1: NAME
                f_car.upper(),                                  # 2: CAR NO
                fd,                                             # 3: DATE
                f_cust.upper() if f_cust else "",               # 4: CUSTOMER
                f_do.upper() if f_do else "",                   # 5: D.O NO
                f_dest.upper() if f_dest else "",               # 6: DESTINATION
                f_tout,                                         # 7: TIME OUT
                f_tin,                                          # 8: TIME IN
                tr,                                             # 9: TRIP TIME
                f_tripno.upper() if f_tripno else "",           # 10: TRIP NO ★
                f_notes.upper() if f_notes else "",             # 11: NOTES
                f_reportno.upper() if f_reportno else "",       # 12: REPORT NO ★
                MY_ID,                                          # 13: CREATED BY
            ]
            with st.spinner("جاري الحفظ..."):
                try:
                    sheet.append_row(row)
                    st.success(f"✅ تم الحفظ! مدة الرحلة: {tr}")
                    st.rerun()
                except Exception as e: st.error(f"❌ {e}")

# ══════════════════════════════════════════
# TAB 3: سجل الحركات
# ══════════════════════════════════════════
with tab_records:
    st.markdown("### 📋 جدول سجلات السائقين (الأحدث أولاً)")
    if not data_rows:
        st.info("لا توجد بيانات.")
    else:
        mc=len(INTERNAL_COLS)
        clean=[]
        for row in data_rows:
            r=(row+[""]*(mc-len(row)))[:mc]
            clean.append(r)

        df=pd.DataFrame(clean,columns=INTERNAL_COLS)
        df['Sheet_Row']=range(HROWS+1, HROWS+1+len(clean))
        df['CREATED BY']=df['CREATED_BY_RAW'].apply(get_display_name)

        ddf=df.iloc[::-1].reset_index(drop=True)

        # جدول HTML موسّط
        html="<div style='overflow-x:auto'><table style='width:100%;border-collapse:collapse;text-align:center;font-size:12px'><thead><tr style='background:#2c3e50;color:#f1c40f'>"
        for c in SHOW_COLS:
            html+=f"<th style='padding:8px 4px;border:1px solid #555'>{COL_LABELS.get(c,c)}</th>"
        html+="</tr></thead><tbody>"
        for _,row in ddf.iterrows():
            html+="<tr>"
            for c in SHOW_COLS:
                val=str(row[c]) if c in row and row[c] else ""
                css="padding:6px 4px;border:1px solid #444;"
                if c=="TRIP TIME" and val: css+="color:#27ae60;font-weight:bold;"
                html+=f"<td style='{css}'>{val}</td>"
            html+="</tr>"
        html+="</tbody></table></div>"
        st.markdown(html,unsafe_allow_html=True)

        # إدارة السجلات
        st.markdown("---")
        with st.expander("⚙️ إدارة السجلات (تعديل / حذف)",expanded=False):
            opts=[]
            for _,r in df.iloc[::-1].iterrows():
                opts.append(f"{r['Sheet_Row']} | SR#{r['SR#']} - {r['NAME']} - {r['DATE']}")
            sel=st.selectbox("اختر السجل:",[""]+opts,key="rs")
            if sel:
                sr_row=int(sel.split(" | ")[0])
                ri=sr_row-HROWS-1
                curr=df[df['Sheet_Row']==sr_row].iloc[0]
                cr_raw=str(clean[ri][13]).strip() if 0<=ri<len(clean) and len(clean[ri])>13 else ""
                cr_norm=normalize_creator(cr_raw); my_norm=normalize_creator(MY_ID)
                can=IS_ADMIN or (my_norm==cr_norm)
                cr_disp=get_display_name(cr_raw)

                if not can:
                    st.error(f"🚫 لا تملك صلاحية! السجل أدخله: **{cr_disp}**. فقط صاحبه أو الأدمن.")
                else:
                    st.success(f"✅ لديك صلاحية — أنت: **{MY_NAME}**")
                    act=st.radio("الإجراء:",["تعديل ✏️","حذف 🗑️"],horizontal=True,key="ar")

                    if act=="حذف 🗑️":
                        dr=st.text_input("سبب الحذف (إلزامي):",key="dr")
                        if st.button("🚨 تأكيد الحذف",type="primary"):
                            if not dr.strip(): st.error("⚠️ أدخل السبب!")
                            else:
                                try:
                                    sheet.delete_rows(sr_row)
                                    log_audit("حذف",f"SR:{curr['SR#']}|{dr}")
                                    st.success("✅ تم!"); st.rerun()
                                except Exception as e: st.error(f"خطأ: {e}")

                    elif act=="تعديل ✏️":
                        st.markdown("##### تعديل السجل")
                        with st.form("ef"):
                            try: pd_=datetime.strptime(curr['DATE'],"%d-%b-%Y").date()
                            except: pd_=datetime.today().date()
                            do=get_drivers(); co=get_customers(); cao=get_car_options(); dso=get_dest_options()
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
                            ti=TIME_SLOTS.index(curr['TIME OUT']) if curr['TIME OUT'] in TIME_SLOTS else 0
                            to=TIME_SLOTS.index(curr['TIME IN']) if curr['TIME IN'] in TIME_SLOTS else 0
                            with e7: etf=st.selectbox("وقت الخروج",TIME_SLOTS,index=ti)
                            with e8: ett=st.selectbox("وقت الوصول",TIME_SLOTS,index=to)
                            # ★ الحقول الجديدة في التعديل
                            e9,e10,e11=st.columns(3)
                            with e9:  etn=st.text_input("رقم الرحلة",value=curr['TRIP NO'])
                            with e10: ern=st.text_input("رقم التقرير",value=curr['REPORT NO'])
                            with e11: en=st.text_input("ملاحظات",value=curr['NOTES'])

                            if st.form_submit_button("💾 حفظ"):
                                etr=trip_dur(TIME_MAP[etf],TIME_MAP[ett])
                                upd=[
                                    curr['SR#'], ed.upper(), ec.upper(),
                                    edt.strftime("%d-%b-%Y").upper(),
                                    ecu.upper() if ecu else "",
                                    edo.upper() if edo else "",
                                    eds.upper() if eds else "",
                                    etf, ett, etr,
                                    etn.upper() if etn else "",     # TRIP NO
                                    en.upper() if en else "",       # NOTES
                                    ern.upper() if ern else "",     # REPORT NO
                                    cr_raw,                         # CREATED BY (أصلي)
                                ]
                                try:
                                    try: sheet.update(range_name=f"A{sr_row}:N{sr_row}",values=[upd])
                                    except TypeError: sheet.update(f"A{sr_row}:N{sr_row}",[upd])
                                    log_audit("تعديل",f"SR:{curr['SR#']}")
                                    st.success(f"✅ تم! مدة الرحلة: {etr}"); st.rerun()
                                except Exception as e: st.error(f"خطأ: {e}")


