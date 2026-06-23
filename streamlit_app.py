import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="سجل حركة السائقين | Dispatch Web", page_icon="🚚", layout="wide")

st.markdown("""<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}</style>""", unsafe_allow_html=True)
st.title("🚚 لوحة مراقبة حركة السائقين (وين طالع / وين جاي)")
st.markdown("---")

conn = st.connection("gsheets", type=GSheetsConnection)

# قراءة أوراق العمل من شيت الجوجل
df_log = conn.read(worksheet="Movement_Log", ttl=5)
df_drivers = conn.read(worksheet="Drivers", ttl=60)
df_customers = conn.read(worksheet="Customers", ttl=60)

drivers_list = df_drivers["Driver_Name"].dropna().tolist() if not df_drivers.empty else ["JAMEEL - 101", "RAFIQ - 102", "KHALID - 103"]
customers_list = df_customers["Customer_Name"].dropna().tolist() if not df_customers.empty else ["عميل نقدي", "شركة دبي للمقاولات", "مصنع الألومنيوم"]
vehicles_list = ["TRUCK - 7412", "PICKUP - 9632", "TESLA - 3", "HIACE - 8520"]

with st.expander("➕ تسجيل حركة سائق جديدة", expanded=True):
    with st.form("dispatch_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            logged_by = st.text_input("👤 الموظفة المسؤولة:", placeholder="مثال: Fatima")
            driver = st.selectbox("👷‍♂️ اختر السائق:", options=[""] + drivers_list)
            vehicle = st.selectbox("🚛 السيارة:", options=[""] + vehicles_list)

        with col2:
            move_type = st.radio("📍 اتجاه الحركة:", options=["🚀 خروج للتوصيل (OUT)", "🏡 عودة للمصنع (IN)"], horizontal=True)
            customer = st.selectbox("🏢 الوجهة / العميل:", options=[""] + customers_list)
            area = st.text_input("المنطقة:", placeholder="مثال: الشارقة - الصناعية 10")

        with col3:
            coo_ref = st.text_input("📑 رقم طلبية COO:", placeholder="مثال: ORD-2026-881")
            notes = st.text_area("✍️ ملاحظات الحمولة:", placeholder="اكتب أي تفاصيل هنا...", height=68)

        submitted = st.form_submit_button("حفظ وتحديث الشيت المباشر 💾", use_container_width=True)

        if submitted:
            if not driver or not logged_by:
                st.error("⚠️ يرجى تحديد اسم السائق والموظفة المسؤولة!")
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
                    "Logged_By": [logged_by]
                })
                updated_df = pd.concat([df_log, new_row], ignore_index=True)
                conn.update(worksheet="Movement_Log", data=updated_df)
                st.success(f"✅ تم تسجيل حركة السائق ({driver}) بنجاح!")
                st.rerun()

st.subheader("📊 جدول مراقبة السائقين الحي (مرتبط بـ Google Drive)")
f_col1, f_col2, f_col3 = st.columns([1, 1, 2])
with f_col1: filter_type = st.selectbox("فلتر حسب الاتجاه:", ["الكل", "🚀 خروج للتوصيل (OUT)", "🏡 عودة للمصنع (IN)"])
with f_col2: filter_driver = st.selectbox("فلتر حسب السائق:", ["الكل"] + drivers_list)

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
            "COO_Ref": "رقم الطلبية", "Notes": "ملاحظات", "Logged_By": "المستخدم"
        }
    )
else:
    st.info("📭 الجدول فارغ حالياً.")
