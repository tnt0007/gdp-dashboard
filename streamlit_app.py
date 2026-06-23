import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. إعدادات الصفحة
st.set_page_config(page_title="حركة السائقين | Al Hamad ERP", page_icon="🚚", layout="wide")
st.markdown("""<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}</style>""", unsafe_allow_html=True)

# 2. ذاكرة الجلسة (Login Session)
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'current_user' not in st.session_state:
    st.session_state['current_user'] = ''

# 3. قائمة الموظفات المصرح لهن بالدخول (الاسم : الرقم السري)
# يمكنك تغيير الأرقام السرية من هنا مباشرة
AUTH_USERS = {
    "Fatima": "1001",
    "Amna": "1002",
    "Maryam": "1003",
    "Admin": "0000",
    "Heitham": "2026"
}

# ══════════════════════════════════════════════════════════════
# بوابة الدخول المحمية (The Gatekeeper)
# ══════════════════════════════════════════════════════════════
if not st.session_state['logged_in']:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.5, 1])
    
    with col2:
        st.markdown("""
        <div style='text-align: center; padding: 20px; background-color: #ffffff; border-radius: 8px; border: 1px solid #e1e8ed;'>
            <h2 style='color: #2c3e50; font-family: ae_AlMothnna, Arial;'>نظام حركة السائقين</h2>
            <p style='color: #7f8c8d; font-size: 14px;'>Al Hamad Aluminium Extrusions</p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("login_card"):
            user_input = st.selectbox("👤 اسم المستخدم | User:", options=[""] + list(AUTH_USERS.keys()))
            pass_input = st.text_input("🔑 الرمز السري | PIN:", type="password")
            
            submit_btn = st.form_submit_button("تسجيل الدخول 🔐", use_container_width=True)

            if submit_btn:
                if user_input and pass_input == AUTH_USERS.get(user_input, ""):
                    st.session_state['logged_in'] = True
                    st.session_state['current_user'] = user_input
                    st.rerun()
                else:
                    st.error("❌ عذراً، اسم المستخدم أو الرمز السري غير صحيح.")
    
    # هذه الكلمة تمنع المتصفح من قراءة أي سطر تحتها حتى يسجل الموظف دخوله
    st.stop()


# ══════════════════════════════════════════════════════════════
# البرنامج الرئيسي (لا يظهر إلا بعد تسجيل الدخول الصحيح)
# ══════════════════════════════════════════════════════════════

# شريط المستخدم العلوي
top1, top2 = st.columns([4, 1])
with top1:
    st.subheader(f"🚚 لوحة التحكم | أهلاً بكِ: {st.session_state['current_user']}")
with top2:
    if st.button("🚪 تسجيل خروج", use_container_width=True):
        st.session_state['logged_in'] = False
        st.session_state['current_user'] = ''
        st.rerun()

st.markdown("---")

# الاتصال المباشر بـ Google Drive
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df_log = conn.read(worksheet="Movement_Log", ttl=5)
    df_drivers = conn.read(worksheet="Drivers", ttl=60)
    df_customers = conn.read(worksheet="Customers", ttl=60)
except Exception as e:
    st.error(f"⚠️ يوجد مشكلة في قراءة شيت الجوجل: {e}")
    st.stop()

drivers_list = df_drivers["Driver_Name"].dropna().tolist() if not df_drivers.empty else ["JAMEEL - 101", "RAFIQ - 102", "KHALID - 103"]
customers_list = df_customers["Customer_Name"].dropna().tolist() if not df_customers.empty else ["عميل نقدي", "شركة دبي للمقاولات", "مصنع الألومنيوم"]
vehicles_list = ["TRUCK - 7412", "PICKUP - 9632", "TESLA - 3", "HIACE - 8520"]

with st.expander("➕ إذن تحرك سائق جديد (Dispatch Entry)", expanded=True):
    with st.form("dispatch_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.info(f"المسؤولة عن الإذن: **{st.session_state['current_user']}**")
            driver = st.selectbox("👷‍♂️ اختر السائق:", options=[""] + drivers_list)
            vehicle = st.selectbox("🚛 السيارة:", options=[""] + vehicles_list)

        with c2:
            move_type = st.radio("📍 نوع الحركة:", options=["🚀 خروج للتوصيل (OUT)", "🏡 عودة للمصنع (IN)"], horizontal=True)
            customer = st.selectbox("🏢 الوجهة / العميل:", options=[""] + customers_list)
            area = st.text_input("المنطقة:", placeholder="مثال: دبي - القوز")

        with c3:
            coo_ref = st.text_input("📑 رقم طلبية COO:", placeholder="مثال: ORD-881")
            notes = st.text_area("✍️ ملاحظات الحمولة:", placeholder="اكتب تفاصيل البضاعة...", height=68)

        save_btn = st.form_submit_button("ترحيل البيانات إلى Google Sheet 💾", use_container_width=True)

        if save_btn:
            if not driver:
                st.error("⚠️ يرجى تحديد اسم السائق أولاً!")
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
                    "Logged_By": [st.session_state['current_user']]  # يسحب الاسم من تسجيل الدخول
                })
                updated_df = pd.concat([df_log, new_row], ignore_index=True)
                conn.update(worksheet="Movement_Log", data=updated_df)
                st.success(f"✅ تم ترحيل حركة ({driver}) إلى جوجل درايف بنجاح!")
                st.rerun()

st.subheader("📊 الجدول الحي لحركة السائقين (Live Google Sheet)")

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
            "Timestamp": "الوقت", "Driver_Name": "السائق", "Movement_Type": "الحركة",
            "Customer_Destination": "العميل", "Area": "المنطقة", "Vehicle": "المركبة",
            "COO_Ref": "رقم الطلب", "Notes": "البيان", "Logged_By": "المُدخلة"
        }
    )
else:
    st.info("📭 لا يوجد حركات مسجلة تطابق هذا الفلتر.")
