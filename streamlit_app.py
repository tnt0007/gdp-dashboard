import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# ══════════════════════════════════════════════════════════════
# 1. إعدادات الصفحة
# ══════════════════════════════════════════════════════════════
st.set_page_config(page_title="حركة السائقين | Al Hamad ERP", page_icon="🚚", layout="wide")

# إخفاء عناصر ستريملت الافتراضية ليعطي مظهر تطبيق مستقل
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# 2. دالة تنظيف الأرقام (حل مشكلة الأرقام العربية ٠١٢٣٤ في الجوالات)
# ══════════════════════════════════════════════════════════════
def clean_digits(val):
    if not val: return ""
    arabic_to_eng = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
    return str(val).translate(arabic_to_eng).strip()

# ══════════════════════════════════════════════════════════════
# 3. قاعدة بيانات المستخدمين (الدخول بالرقم الوظيفي)
# الصيغة: "الرقم الوظيفي": {"name": "اسم الموظف/ـة", "pin": "الرمز السري"}
# ══════════════════════════════════════════════════════════════
USERS_DB = {
    "1000": {"name": "الإدارة | Admin", "pin": "0000"},
    "2026": {"name": "Heitham Seddiqi", "pin": "2026"},
    "1001": {"name": "Fatima", "pin": "1001"},
    "1002": {"name": "Amna", "pin": "1002"},
    "1003": {"name": "Maryam", "pin": "1003"}
}

# تهيئة الجلسة
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'current_user_id' not in st.session_state:
    st.session_state['current_user_id'] = ''
if 'current_user_name' not in st.session_state:
    st.session_state['current_user_name'] = ''

# ══════════════════════════════════════════════════════════════
# 4. بوابة الدخول المحمية (Login Gate)
# ══════════════════════════════════════════════════════════════
if not st.session_state['logged_in']:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.5, 1])
    
    with col2:
        st.markdown("""
        <div style='text-align: center; padding: 15px; background-color: #ffffff; border-radius: 8px; border: 1px solid #e1e8ed; margin-bottom: 20px;'>
            <h2 style='color: #2c3e50; font-family: ae_AlMothnna, Arial; margin-bottom: 5px;'>نظام حركة السائقين</h2>
            <p style='color: #7f8c8d; font-size: 14px; margin-top: 0;'>Al Hamad Aluminium Extrusions Factory</p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("login_form"):
            emp_id_input = st.text_input("💳 الرقم الوظيفي | Employee ID:", placeholder="أدخل رقمك الوظيفي (مثال: 1000 أو 1001)")
            pin_input = st.text_input("🔑 الرمز السري | PIN:", type="password", placeholder="أدخل الرمز السري")
            
            submit_btn = st.form_submit_button("دخول | Login 🔐", use_container_width=True)

            if submit_btn:
                clean_id = clean_digits(emp_id_input)
                clean_pin = clean_digits(pin_input)
                
                if not clean_id or not clean_pin:
                    st.warning("⚠️ يرجى إدخال الرقم الوظيفي والرمز السري.")
                elif clean_id in USERS_DB and USERS_DB[clean_id]["pin"] == clean_pin:
                    st.session_state['logged_in'] = True
                    st.session_state['current_user_id'] = clean_id
                    st.session_state['current_user_name'] = USERS_DB[clean_id]["name"]
                    st.rerun()
                else:
                    st.error("❌ الرقم الوظيفي أو الرمز السري غير صحيح.")
    
    st.stop()

# ══════════════════════════════════════════════════════════════
# 5. واجهة البرنامج الرئيسية (بعد تسجيل الدخول الصحيح)
# ══════════════════════════════════════════════════════════════

# الترويسة العلوية ومعلومات المستخدم
top1, top2 = st.columns([4, 1])
with top1:
    st.subheader(f"🚚 لوحة التحكم | أهلاً بك: **{st.session_state['current_user_name']}** (ID: {st.session_state['current_user_id']})")
with top2:
    if st.button("🚪 تسجيل خروج", use_container_width=True):
        st.session_state['logged_in'] = False
        st.session_state['current_user_id'] = ''
        st.session_state['current_user_name'] = ''
        st.rerun()

st.markdown("---")

# الاتصال بقاعدة بيانات Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df_log = conn.read(worksheet="Movement_Log", ttl=5)
except Exception as e:
    st.error(f"⚠️ يوجد مشكلة في قراءة السجل 'Movement_Log' من شيت الجوجل: {e}")
    st.stop()

# قراءة قائمة السائقين من الشيت
try:
    df_drivers = conn.read(worksheet="Drivers", ttl=60)
    drivers_list = df_drivers["Driver_Name"].dropna().tolist() if not df_drivers.empty else []
except: drivers_list = []
if not drivers_list: drivers_list = ["101 - JAMEEL", "102 - RAFIQ", "103 - KHALID"]

# قراءة قائمة العملاء من الشيت
try:
    df_customers = conn.read(worksheet="Customers", ttl=60)
    customers_list = df_customers["Customer_Name"].dropna().tolist() if not df_customers.empty else []
except: customers_list = []
if not customers_list: customers_list = ["عميل نقدي", "شركة دبي للمقاولات", "مصنع الألومنيوم"]

vehicles_list = ["TRUCK - 7412", "PICKUP - 9632", "TESLA - 3", "HIACE - 8520"]

# ══════════════════════════════════════════════════════════════
# نموذج تسجيل التحرك
# ══════════════════════════════════════════════════════════════
with st.expander("➕ تسجيل حركة سائق جديدة (New Dispatch Entry)", expanded=True):
    with st.form("dispatch_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.text_input("👤 الموظف/ـة المسؤولة:", value=st.session_state['current_user_name'], disabled=True)
            driver = st.selectbox("👷‍♂️ اختر السائق:", options=[""] + drivers_list)
            vehicle = st.selectbox("🚛 السيارة:", options=[""] + vehicles_list)

        with c2:
            move_type = st.radio("📍 نوع الحركة:", options=["🚀 خروج للتوصيل (OUT)", "🏡 عودة للمصنع (IN)"], horizontal=True)
            customer = st.selectbox("🏢 الوجهة / العميل:", options=[""] + customers_list)
            area = st.text_input("المنطقة:", placeholder="مثال: دبي - القوز الصناعية")

        with c3:
            coo_ref = st.text_input("📑 رقم طلبية COO:", placeholder="مثال: ORD-2026-881")
            notes = st.text_area("✍️ ملاحظات الحمولة:", placeholder="اكتب أي تفاصيل إضافية هنا...", height=68)

        save_btn = st.form_submit_button("ترحيل وحفظ في Google Drive 💾", use_container_width=True)

        if save_btn:
            if not driver:
                st.error("⚠️ يرجى تحديد اسم السائق!")
            else:
                new_row = pd.DataFrame({
                    "Timestamp": [datetime.now().strftime("%d-%b-%Y %H:%M:%S")],
                    "Driver_Name": [driver],
                    "Movement_Type": [move_type],
                    "Customer_Destination": [customer],
                    "Area": [area],
                    "Vehicle": [vehicle],
                    "COO_Ref": [coo_ref],
                    "Notes": [notes],
                    "Logged_By": [st.session_state['current_user_name']]
                })
                updated_df = pd.concat([df_log, new_row], ignore_index=True)
                conn.update(worksheet="Movement_Log", data=updated_df)
                st.success(f"✅ تم تسجيل حركة السائق ({driver}) بنجاح!")
                st.rerun()

# ══════════════════════════════════════════════════════════════
# عرض الجدول الحي
# ══════════════════════════════════════════════════════════════
st.subheader("📊 الجدول المباشر لحركة السائقين (مرتبط بـ Google Sheet)")

f1, f2, f3 = st.columns([1, 1, 2])
with f1: filter_type = st.selectbox("فلتر الاتجاه:", ["الكل", "🚀 خروج للتوصيل (OUT)", "🏡 عودة للمصنع (IN)"])
with f2: filter_driver = st.selectbox("فلتر السائقين:", ["الكل"] + drivers_list)

filtered_df = df_log.copy()
if filter_type != "الكل": filtered_df = filtered_df[filtered_df["Movement_Type"] == filter_type]
if filter_driver != "الكل": filtered_df = filtered_df[filtered_df["Driver_Name"] == filter_driver]

if not filtered_df.empty:
    st.dataframe(
        filtered_df.iloc[::-1],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Timestamp": "الوقت والتاريخ", "Driver_Name": "اسم السائق", "Movement_Type": "الحركة",
            "Customer_Destination": "العميل / الوجهة", "Area": "المنطقة", "Vehicle": "السيارة",
            "COO_Ref": "رقم الطلبية", "Notes": "البيان", "Logged_By": "المُدخلة"
        }
    )
else:
    st.info("📭 لا توجد سجلات تطابق الفلتر الحالي.")
