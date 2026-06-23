import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import sqlite3
import os
import pandas as pd
from datetime import datetime, timedelta
from PIL import Image

# ==========================================
# 1. إعدادات الصفحة وخط Tahoma
# ==========================================
st.set_page_config(page_title="حركة السائقين | Al Hamad", page_icon="🚛", layout="wide")

st.markdown("""
    <style>
    html, body, [class*="css"] { 
        font-family: 'Tahoma', sans-serif !important; 
    }
    h1, h2, h3 { color: #f1c40f !important; text-align: center; }
    label, .st-bb { font-size: 14px !important; color: #95a5a6 !important; font-weight: bold; }
    .stButton>button { background-color: #2980b9; color: white; border-radius: 5px; width: 100%; font-weight: bold; border: none; }
    .stButton>button:hover { background-color: #3498db; border: 1px solid #f1c40f; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. المسارات (OneDrive)
# ==========================================
USER_HOME = os.path.expanduser("~")
_P1 = os.path.join(USER_HOME, "OneDrive - al hamad aluminum extrusions", "22-02-2022", "ERP")
_P2 = os.path.join(USER_HOME, "OneDrive - al hamad aluminum extrusions", "haitham seddiqi's files - 22-02-2022", "ERP")
_P3 = os.getcwd()

BASE_DIR = _P3
for _p in [_P1, _P2, _P3]:
    if os.path.exists(_p) and os.path.exists(os.path.join(_p,"confirmation_orders.db")):
        BASE_DIR = _p; break

DB_MAIN    = os.path.join(BASE_DIR, "confirmation_orders.db")
HR_DB      = os.path.join(BASE_DIR, "factory_erp.db")
EMP_PIC_DIR = os.path.join(BASE_DIR, "pic")
LOGO_PATH  = os.path.join(BASE_DIR, "logo2.jpg")

# ==========================================
# 3. دوال جلب البيانات
# ==========================================
@st.cache_data(ttl=60)
def get_customers():
    try:
        conn = sqlite3.connect(DB_MAIN)
        c = conn.cursor()
        c.execute("SELECT name FROM customers ORDER BY name")
        res = [r[0] for r in c.fetchall()]
        conn.close()
        return [""] + res
    except: return [""]

@st.cache_data(ttl=60)
def get_drivers():
    try:
        conn = sqlite3.connect(HR_DB)
        c = conn.cursor()
        c.execute("PRAGMA table_info(employees)")
        cols = [col[1].lower() for col in c.fetchall()]
        
        filter_query = "SELECT name_ar, name FROM employees WHERE status NOT LIKE '%كنسل%'"
        for cand in ['designation', 'department', 'job_title']:
            if cand in cols:
                filter_query += f" AND ({cand} LIKE '%سائق%' OR {cand} LIKE '%driver%')"
                break
                
        c.execute(filter_query)
        # جلب الاسم الإنجليزي (name) كأولوية
        res = [str(r[1] if r[1] else r[0]) for r in c.fetchall()]
        conn.close()
        return [""] + res
    except: return [""]

# ==========================================
# 4. إدارة الجلسة وتحديث السجلات
# ==========================================
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'username' not in st.session_state: st.session_state['username'] = ""
if 'real_name' not in st.session_state: st.session_state['real_name'] = ""

def verify_login(username, password):
    try:
        conn = sqlite3.connect(DB_MAIN, timeout=5000)
        c = conn.cursor()
        c.execute("SELECT role FROM app_users WHERE username=? AND password=?", (username, password))
        res = c.fetchone()
        conn.close()
        
        if res:
            real_name = username
            if os.path.exists(HR_DB):
                try:
                    c_hr = sqlite3.connect(HR_DB).cursor()
                    c_hr.execute("SELECT name_ar, name FROM employees WHERE emp_id=?", (username,))
                    r_hr = c_hr.fetchone()
                    if r_hr:
                        fn = r_hr[0] if r_hr[0] else r_hr[1]
                        real_name = str(fn).split()[0] if fn else username
                except: pass
            
            st.session_state['logged_in'] = True
            st.session_state['username'] = username
            st.session_state['real_name'] = real_name
            st.rerun()
        else:
            st.error("❌ بيانات الدخول غير صحيحة")
    except Exception as e:
        st.error(f"⚠️ خطأ في الاتصال: {e}")

def logout():
    st.session_state['logged_in'] = False
    st.session_state['username'] = ""
    st.session_state['real_name'] = ""
    st.rerun()

def log_audit(action, details):
    try:
        conn = sqlite3.connect(DB_MAIN)
        c = conn.cursor()
        c.execute("INSERT INTO audit_trail (user, action, timestamp, details) VALUES (?, ?, ?, ?)",
                  (st.session_state['real_name'], action, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), details))
        conn.commit()
        conn.close()
    except: pass

# ==========================================
# 5. شاشة تسجيل الدخول
# ==========================================
if not st.session_state['logged_in']:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([2,1,2])
    if os.path.exists(LOGO_PATH):
        with col2: st.image(LOGO_PATH, width=80, use_column_width=False)
        
    st.title("نظام حركة السائقين")
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<h3 style='color: white;'>تسجيل الدخول | Login 🔐</h3>", unsafe_allow_html=True)
        with st.form("login_form"):
            username_input = st.text_input("اسم المستخدم | Username")
            password_input = st.text_input("كلمة المرور | Password", type="password")
            submit_btn = st.form_submit_button("دخول")
            if submit_btn:
                if username_input and password_input: verify_login(username_input, password_input)
                else: st.warning("يرجى إدخال جميع البيانات.")

# ==========================================
# 6. الواجهة الرئيسية
# ==========================================
else:
    with st.sidebar:
        st.markdown("<h2 style='color:#f1c40f;'>الملف الشخصي</h2>", unsafe_allow_html=True)
        pic_found = False
        for ext in [".jpg", ".jpeg", ".png"]:
            pic_path = os.path.join(EMP_PIC_DIR, f"{st.session_state['username']}{ext}")
            if os.path.exists(pic_path):
                try:
                    img = Image.open(pic_path)
                    st.image(img, width=120)
                    pic_found = True
                    break
                except: pass
        if not pic_found: st.info("لا توجد صورة | No Image")
        st.markdown(f"### أهلاً بك | Welcome\n**{st.session_state['real_name']}**")
        st.markdown("---")
        st.button("🔒 تسجيل خروج | Logout", on_click=logout)

    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open("Drivers_Report").sheet1
        sheet_data = sheet.get_all_values()
        next_serial = len(sheet_data) if len(sheet_data) > 0 else 1
        connection_status = True
    except Exception as e:
        connection_status = False

    col_logo, col_title = st.columns([1, 4])
    if os.path.exists(LOGO_PATH):
        with col_logo: st.image(LOGO_PATH, width=60)
    with col_title:
        st.title("🚛 إدخال حركة السائقين")

    st.markdown("---")

    if not connection_status:
        st.error("⚠️ لم يتمكن البرنامج من الاتصال بجوجل شيت. تأكد من إعدادات الربط.")
        st.stop()

    # --- نموذج الإدخال الجديد ---
    with st.form("driver_form", clear_on_submit=True):
        st.markdown(f"<div style='text-align: left; color: #3498db; font-weight: bold;'>الرقم التسلسلي (SR#): {next_serial}</div>", unsafe_allow_html=True)
        
        c1, c2, c3, c4 = st.columns(4)
        with c1: driver_name = st.selectbox("اسم السائق | NAME", options=get_drivers())
        with c2: car_no = st.text_input("رقم السيارة | CAR NO")
        with c3: date_input = st.date_input("التاريخ | DATE")
        with c4: customer = st.selectbox("العميل | CUSTOMER", options=get_customers())

        c5, c6, c7, c8 = st.columns(4)
        with c5: do_no = st.text_input("رقم التوصيل | D.O NO")
        with c6: destination = st.text_input("الموقع | DESTINATION")
        with c7: time_from = st.time_input("الوقت من | TIME FROM")
        with c8: time_to = st.time_input("الوقت إلى | TIME TO")
        
        notes = st.text_input("الملاحظات | NOTS")
        
        st.markdown("<br>", unsafe_allow_html=True)
        submit_button = st.form_submit_button(label="💾 حفظ البيانات وإضافتها للجدول")

    if submit_button:
        if not driver_name or not car_no:
            st.warning("⚠️ يرجى تعبئة اسم السائق ورقم السيارة على الأقل.")
        else:
            formatted_date = date_input.strftime("%d-%b-%Y")
            f_time_from = time_from.strftime("%H:%M")
            f_time_to = time_to.strftime("%H:%M")
            
            t1 = datetime.combine(datetime.today(), time_from)
            t2 = datetime.combine(datetime.today(), time_to)
            if t2 < t1: t2 += timedelta(days=1)
            diff = t2 - t1
            total_time = f"{diff.seconds//3600:02d}:{(diff.seconds//60)%60:02d}"
            
            row_data = [
                next_serial, driver_name, car_no, formatted_date, customer, do_no, destination,
                f_time_from, f_time_to, total_time, "", notes, "", st.session_state['real_name']
            ]
            
            with st.spinner('جاري الحفظ...'):
                try:
                    sheet.append_row(row_data)
                    st.success("✅ تم حفظ البيانات بنجاح!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ حدث خطأ: {e}")

    st.markdown("---")
    st.markdown("### 📋 جدول سجلات السائقين (الأحدث أولاً)")
    
    if len(sheet_data) > 1:
        headers = sheet_data[0] 
        df = pd.DataFrame(sheet_data[1:], columns=headers)
        df['Row_Num'] = range(2, len(sheet_data) + 1)
        
        # عرض الجدول بشكل أنيق
        st.dataframe(df.iloc[::-1].drop(columns=['Row_Num']), use_container_width=True)
        
        # --- قسم إدارة السجلات (التعديل والحذف) ---
        with st.expander("⚙️ إدارة السجلات (تعديل / حذف)"):
            record_list = df['Row_Num'].astype(str) + " - " + df.iloc[:,1] + " | " + df.iloc[:,3]
            selected_rec = st.selectbox("اختر السجل المطلوب من القائمة:", [""] + record_list.tolist())
            
            if selected_rec:
                row_idx = int(selected_rec.split(" - ")[0])
                curr_data = df[df['Row_Num'] == row_idx].iloc[0]
                
                action = st.radio("نوع الإجراء:", ["تعديل البيانات ✏️", "حذف السجل 🗑️"], horizontal=True)
                
                # --- برمجة الحذف ---
                if action == "حذف السجل 🗑️":
                    del_reason = st.text_input("سبب الحذف (إلزامي للتأكيد):", key="del_reason")
                    if st.button("🚨 تأكيد الحذف نهائياً", type="primary"):
                        if not del_reason.strip():
                            st.error("⚠️ يجب إدخال سبب الحذف!")
                        else:
                            try:
                                sheet.delete_rows(row_idx)
                                log_audit("حذف سجل سائق", f"Row: {row_idx} | SR: {curr_data.iloc[0]} | Reason: {del_reason}")
                                st.success("تم الحذف بنجاح!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"خطأ في الحذف: {e}")
                
                # --- برمجة التعديل ---
                elif action == "تعديل البيانات ✏️":
                    st.markdown("#### تعديل بيانات السجل")
                    with st.form("edit_form"):
                        try: p_date = datetime.strptime(curr_data.iloc[3], "%d-%b-%Y").date()
                        except: p_date = datetime.today().date()
                        try: p_tfrom = datetime.strptime(curr_data.iloc[7], "%H:%M").time()
                        except: p_tfrom = datetime.now().time()
                        try: p_tto = datetime.strptime(curr_data.iloc[8], "%H:%M").time()
                        except: p_tto = datetime.now().time()
                        
                        d_opts = get_drivers()
                        c_opts = get_customers()
                        curr_driver = curr_data.iloc[1]
                        curr_cust = curr_data.iloc[4]
                        
                        ec1, ec2, ec3, ec4 = st.columns(4)
                        with ec1: e_driver = st.selectbox("الاسم", options=d_opts, index=d_opts.index(curr_driver) if curr_driver in d_opts else 0)
                        with ec2: e_car = st.text_input("رقم السيارة", value=curr_data.iloc[2])
                        with ec3: e_date = st.date_input("التاريخ", value=p_date)
                        with ec4: e_cust = st.selectbox("العميل", options=c_opts, index=c_opts.index(curr_cust) if curr_cust in c_opts else 0)
                        
                        ec5, ec6, ec7, ec8 = st.columns(4)
                        with ec5: e_do = st.text_input("رقم التوصيل", value=curr_data.iloc[5])
                        with ec6: e_dest = st.text_input("الموقع", value=curr_data.iloc[6])
                        with ec7: e_tfrom = st.time_input("الوقت من", value=p_tfrom)
                        with ec8: e_tto = st.time_input("الوقت إلى", value=p_tto)
                        
                        e_notes = st.text_input("الملاحظات", value=curr_data.iloc[11])
                        save_edit = st.form_submit_button("💾 حفظ التعديلات")
                        
                        if save_edit:
                            t1 = datetime.combine(datetime.today(), e_tfrom)
                            t2 = datetime.combine(datetime.today(), e_tto)
                            if t2 < t1: t2 += timedelta(days=1)
                            diff = t2 - t1
                            e_total = f"{diff.seconds//3600:02d}:{(diff.seconds//60)%60:02d}"
                            
                            updated_row = [
                                curr_data.iloc[0], e_driver, e_car, e_date.strftime("%d-%b-%Y"),
                                e_cust, e_do, e_dest, e_tfrom.strftime("%H:%M"), e_tto.strftime("%H:%M"),
                                e_total, "", e_notes, "", curr_data.iloc[13]
                            ]
                            
                            try:
                                try:
                                    sheet.update(range_name=f"A{row_idx}:N{row_idx}", values=[updated_row])
                                except TypeError:
                                    sheet.update(f"A{row_idx}:N{row_idx}", [updated_row])
                                    
                                log_audit("تعديل سجل سائق", f"Row: {row_idx} | SR: {curr_data.iloc[0]}")
                                st.success("تم التعديل بنجاح!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"خطأ أثناء التعديل: {e}")
    else:
        st.info("لا توجد بيانات مسجلة حتى الآن في الجدول.")
