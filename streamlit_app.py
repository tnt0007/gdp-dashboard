import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import pandas as pd
from decimal import Decimal, ROUND_HALF_UP

# ══════════════════════════════════════════════════════════════
# 1. إعدادات الصفحة والمظهر القياسي (التركيز على الأداء الوظيفي)
# ══════════════════════════════════════════════════════════════
st.set_page_config(page_title="نظام تأكيد الطلبات - واجهة الويب", layout="centered", initial_sidebar_state="collapsed")

# إلزام التطبيق بالمظهر الفاتح القياسي لمنع التشويش البصري
st.markdown("""
    <style>
    .reportview-container { background: #ffffff; }
    h1, h2, h3, p, label { font-family: 'Arial', sans-serif; color: #333333; }
    .stButton>button { width: 100%; background-color: #2ecc71; color: white; border-radius: 5px; }
    </style>
""", unsafe_allow_html=True)

# دالة التقريب التجاري المطابقة للحسابات اليدوية والملف الأصلي
def _cround(v, d=2):
    try:
        return float(Decimal(str(float(v))).quantize(Decimal(10)**-d, rounding=ROUND_HALF_UP))
    except:
        return round(float(v), d)

# ══════════════════════════════════════════════════════════════
# 2. الربط الآمن مع Google Sheets
# ══════════════════════════════════════════════════════════════
@st.cache_resource
def get_google_sheet():
    # يتم وضع ملف الـ JSON الخاص بـ Google Cloud Service Account في Streamlit Secrets للأمان
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    # افتح الشيت الخاص بك باستخدام الرابط أو الاسم
    sheet = client.open_by_key(st.secrets["spreadsheet_key"])
    return sheet

try:
    main_sheet = get_google_sheet()
    # جلب قوائم الموظفين والعملاء المحدثة من الشيت المربوط بـ OneDrive
    emp_df = pd.DataFrame(main_sheet.worksheet("Employees").get_all_records())
    cust_df = pd.DataFrame(main_sheet.worksheet("Customers").get_all_records())
    data_entry_ws = main_sheet.worksheet("Data_Entry")
except Exception as e:
    st.error("خطأ في الاتصال بقاعدة بيانات جوجل شيت. يرجى التحقق من الإعدادات.")
    st.stop()

# ══════════════════════════════════════════════════════════════
# 3. نظام التحقق والدخول للموظفين
# ══════════════════════════════════════════════════════════════
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False
    st.session_state['user_id'] = ""
    st.session_state['user_name'] = ""

if not st.session_state['authenticated']:
    st.title("تسجيل الدخول | Login")
    emp_id_input = st.text_input("الرقم الوظيفي | Employee ID")
    passcode = st.text_input("كلمة المرور | Passcode", type="password")
    
    if st.button("دخول | Login"):
        # التحقق من وجود الرقم الوظيفي في القائمة المستوردة
        user_row = emp_df[emp_df['emp_id'].astype(str) == emp_id_input.strip()]
        if not user_row.empty and passcode == "1234":  # يمكن تعديل آلية التحقق حسب الرغبة
            st.session_state['authenticated'] = True
            st.session_state['user_id'] = emp_id_input.strip()
            st.session_state['user_name'] = user_row.iloc[0]['name_ar'] or user_row.iloc[0]['name']
            st.rerun()
        else:
            st.error("الرقم الوظيفي أو كلمة المرور غير صحيحة.")
else:
    # ══════════════════════════════════════════════════════════════
    # 4. واجهة إدخال البيانات (متوافقة بالكامل مع الهاتف والأيباد)
    # ══════════════════════════════════════════════════════════════
    st.subheader(f"مرحباً: {st.session_state['user_name']} ({st.session_state['user_id']})")
    
    if st.button("تسجيل الخروج | Logout"):
        st.session_state['authenticated'] = False
        st.rerun()
        
    st.title("نظام تأكيد الطلبات والادخال")
    st.write("يرجى ملء الحقول التالية بدقة، وسيتم ترحيل البيانات تلقائياً للشيت الرئيسي.")

    with st.form("entry_form", clear_on_submit=True):
        # توحيد التواريخ تلقائياً بالصيغة المطلوبة dd-Mon-yyyy
        current_date_str = datetime.now().strftime("%d-%b-%Y")
        st.info(f"تاريخ المعاملة الافتراضي: {current_date_str}")
        
        # اختيار العميل من قائمة ديناميكية مستوردة لمنع أخطاء الكتابة
        customer_options = cust_df['customer_name'].tolist() if not cust_df.empty else ["عميل عام"]
        selected_customer = st.selectbox("اسم العميل | Customer Name", options=customer_options)
        
        order_no = st.text_input("رقم الطلب / الفاتورة | Order No")
        amount = st.number_input("المبلغ الأساسي | Basic Amount", min_value=0.0, step=0.1, format="%.2f")
        
        # خيار VAT الخارجي أو الداخلي كما هو متبع في نظامك الخاص بالـ COO
        vat_type = st.radio("نوع الضريبة | VAT Type", options=["VAT 5% خارجي", "شامل الضريبة", "معفي من الضريبة"])
        
        # حقل الملاحظات
        notes = st.text_area("ملاحظات إضافية | Remarks")
        
        submit_btn = st.form_submit_form_button("ترحيل البيانات وحفظ المعاملة | Submit")
        
        if submit_btn:
            if not order_no:
                st.error("يرجى إدخال رقم الطلب أولاً.")
            else:
                # العمليات الحسابية والتقريب التجاري
                if vat_type == "VAT 5% خارجي":
                    calculated_vat = _cround(amount * 0.05)
                    total_amount = _cround(amount + calculated_vat)
                    base_amount = _cround(amount)
                elif vat_type == "شامل الضريبة":
                    total_amount = _cround(amount)
                    base_amount = _cround(total_amount / 1.05)
                    calculated_vat = _cround(total_amount - base_amount)
                else:
                    base_amount = _cround(amount)
                    calculated_vat = 0.0
                    total_amount = _cround(amount)
                
                # إعداد سجل مراقبة العمليات (Audit Trail)
                timestamp_now = datetime.now().strftime("%d-%b-%Y %H:%M:%S")
                
                # تجهيز السطر للترحيل إلى Google Sheets بالترتيب المطابق للشيت الخاص بك
                row_to_insert = [
                    current_date_str, 
                    order_no, 
                    selected_customer, 
                    base_amount, 
                    calculated_vat, 
                    total_amount, 
                    st.session_state['user_name'], 
                    st.session_state['user_id'], 
                    notes,
                    timestamp_now  # سجل مراقبة العمليات
                ]
                
                # ترحيل السطر إلى الشيت
                data_entry_ws.append_row(row_to_insert)
                st.success(f"تم ترحيل الطلب رقم {order_no} بنجاح إلى قاعدة البيانات وتحديث الجداول.")
