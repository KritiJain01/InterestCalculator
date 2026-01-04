import streamlit as st
import pandas as pd
import io
from datetime import date
from fpdf import FPDF

# --- INITIALIZE SESSION STATE ---
if 'bills_df' not in st.session_state:
    st.session_state.bills_df = pd.DataFrame()
if 'trans_df' not in st.session_state:
    st.session_state.trans_df = pd.DataFrame()
if 'files_loaded' not in st.session_state:
    st.session_state.files_loaded = False
# Flags to prevent overwriting manual changes with file uploads on rerun
if 'bills_processed' not in st.session_state:
    st.session_state.bills_processed = False
if 'trans_processed' not in st.session_state:
    st.session_state.trans_processed = False

# --- PDF GENERATION ---
def create_customer_consolidated_pdf(customer, stmt_date, bills_df, trans_df, gst_rate=0.18):
    def pdf_currency(v):
        return f"Rs. {v:,.2f}"

    pdf = FPDF()
    pdf.add_page()

    # Header
    pdf.set_font("Arial", 'B', 18)
    pdf.cell(0, 10, "CUSTOMER CONSOLIDATED STATEMENT", ln=True, align='C')

    pdf.set_font("Arial", '', 10)
    print_date = stmt_date.strftime('%d %b, %Y')
    pdf.cell(0, 7, f"Customer: {customer}", ln=True, align='C')
    pdf.cell(0, 7, f"Statement Date: {print_date}", ln=True, align='C')
    pdf.ln(8)

    # Summary Calculations
    total_original = bills_df['Original Amount'].sum()
    total_balance = bills_df['Balance'].sum()
    total_interest = 0
    total_live_interest = 0
    ageing = {"0-30": 0, "31-60": 0, "61-90": 0, "90+": 0}

    for _, bill in bills_df.iterrows():
        days = max(0, (stmt_date - bill['Due Date']).days)
        live_int = (bill['Balance'] * bill['Rate'] / 100 * days) / 365
        bill_int = trans_df[trans_df['Bill_ID'] == bill['ID']]['Interest Charged'].sum()
        total_interest += bill_int
        total_live_interest += bill_int + live_int

        if days <= 30:
            ageing["0-30"] += bill['Balance']
        elif days <= 60:
            ageing["31-60"] += bill['Balance']
        elif days <= 90:
            ageing["61-90"] += bill['Balance']
        else:
            ageing["90+"] += bill['Balance']

    gst = total_live_interest * gst_rate
    net_due = total_balance + total_live_interest + gst

    # Summary Table
    pdf.set_font("Arial", 'B', 9)
    pdf.set_fill_color(200, 200, 200)
    pdf.cell(130, 10, "Summary", 1, 0, 'C', True)
    pdf.cell(60, 10, "Amount", 1, 1, 'C', True)

    pdf.set_font("Arial", '', 9)
    summary_rows = [
        ("Outstanding Principal", total_balance),
        (f"Interest (Inclusive of Outstanding Principal as of {print_date})", total_live_interest),
        ("GST @ 18%", gst),
        (f"Total Payable Interest", total_live_interest+gst),
        ("Net Payable Amount", net_due),
    ]

    for k, v in summary_rows:
        pdf.cell(130, 10, k, 1)
        pdf.cell(60, 10, pdf_currency(v), 1, 1, 'R')

    # All Transactions Summary Table
    pdf.ln(6)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "All Transactions Summary", ln=True)

    all_trans = trans_df[trans_df['Bill_ID'].isin(bills_df['ID'])]
    if not all_trans.empty:
        pdf.set_font("Arial", 'B', 7)
        pdf.set_fill_color(200, 200, 200)
        trans_summary_widths = [24, 20, 20, 22, 30, 12, 12, 50]
        trans_headers = ["Bill ID", "Due Date", "Pay Date", "Balance", "Amount Paid", "Days", "ROI%", "Interest"]
        
        for i, h in enumerate(trans_headers):
            pdf.cell(trans_summary_widths[i], 7, h, 1, 0, 'C', True)
        pdf.ln()
        
        pdf.set_font("Arial", '', 6)
        for _, t in all_trans.iterrows():
            bill_info = bills_df[bills_df['ID'] == t['Bill_ID']].iloc[0]
            pdf.cell(trans_summary_widths[0], 7, str(t['Bill_ID'])[:10], 1, 0, 'C')
            pdf.cell(trans_summary_widths[1], 7, str(bill_info['Due Date'])[:10], 1, 0, 'C')
            pdf.cell(trans_summary_widths[2], 7, str(t['Date'])[:10], 1, 0, 'C')
            pdf.cell(trans_summary_widths[3], 7, pdf_currency(t['Principal for Interest']), 1, 0, 'R')
            pdf.cell(trans_summary_widths[4], 7, pdf_currency(t['Amount Paid']), 1, 0, 'R')
            pdf.cell(trans_summary_widths[5], 7, str(t['Delayed Days']), 1, 0, 'C')
            pdf.cell(trans_summary_widths[6], 7, f"{bill_info['Rate']}%", 1, 0, 'C')
            pdf.cell(trans_summary_widths[7], 7, pdf_currency(t['Interest Charged']), 1, 1, 'R')
        
        
        pdf.set_font("Arial", 'B', 7)
        pdf.set_fill_color(245, 245, 245)
        for i in range(0, 4):
            pdf.cell(trans_summary_widths[i], 7, "", 1, 0, 'C', True)
        pdf.cell(trans_summary_widths[4]+trans_summary_widths[5]+trans_summary_widths[6], 7, "TOTAL INTEREST", 1, 0, 'C', True)
        total_interest_charged = all_trans['Interest Charged'].sum()
        pdf.cell(trans_summary_widths[7], 7, pdf_currency(total_interest_charged), 1, 1, 'R', True)
        
        pdf.set_font("Arial", 'B', 7)
        pdf.set_fill_color(245, 245, 245)
        for i in range(0, 4):
            pdf.cell(trans_summary_widths[i], 7, "", 1, 0, 'C', True)
        pdf.cell(trans_summary_widths[4]+trans_summary_widths[5]+trans_summary_widths[6], 7, "GST@18%", 1, 0, 'C', True)
        gst_charged = total_interest_charged*0.18
        pdf.cell(trans_summary_widths[7], 7, pdf_currency(gst_charged), 1, 1, 'R', True)
        
        pdf.set_font("Arial", 'B', 7)
        pdf.set_fill_color(245, 245, 245)
        for i in range(0, 4):
            pdf.cell(trans_summary_widths[i], 7, "", 1, 0, 'C', True)
        pdf.cell(trans_summary_widths[4]+trans_summary_widths[5]+trans_summary_widths[6], 7, "TOTAL PAYABLE INTEREST", 1, 0, 'C', True)
        pdf.cell(trans_summary_widths[7], 7, pdf_currency(total_interest_charged+gst_charged), 1, 1, 'R', True)

    # Individual Bill Details
    pdf.ln(6)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Individual Bill Details", ln=True)

    for idx, bill in bills_df.iterrows():
        if pdf.get_y() > 180:
            pdf.add_page()

        # Bill Header with color coding
        bill_trans = trans_df[trans_df['Bill_ID'] == bill['ID']]
        days_overdue = max(0, (stmt_date - bill['Due Date']).days)
        live_int = (bill['Balance'] * bill['Rate'] / 100 * days_overdue) / 365
        total_int_due = bill_trans['Interest Charged'].sum() + live_int

        if bill['Status'] == 'Fully Paid':
            pdf.set_fill_color(240, 255, 240)  # Light green for fully paid
        else:
            pdf.set_fill_color(240, 240, 240)  # Light grey for pending
        
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 8, f"Bill #{bill['ID']} - {bill['Status']}", 1, ln=True, fill=True)

        # Individual Bill Summary Table (Full detail like original)
        pdf.set_font("Arial", 'B', 8)
        pdf.set_fill_color(200, 200, 200)
        bill_widths = [110, 20, 60]
        pdf.cell(bill_widths[0], 8, "", 1, 0, 'C', True)
        pdf.cell(bill_widths[1], 8, "", 1, 0, 'C', True)
        pdf.cell(bill_widths[2], 8, "Amount", 1, 1, 'C', True)

        pdf.set_font("Arial", '', 8)
        
        # Bill-specific calculations with GST
        bill_gst = total_int_due * gst_rate
        bill_net_due = bill['Balance'] + total_int_due + bill_gst

        if bill['Status'] != 'Fully Paid':
            bill_rows = [
                ("Principal Balance", bill['Balance']),
                ("Interest Due", total_int_due),
                ("GST @ 18%", bill_gst),
                ("Total Interest (Incl. GST)", total_int_due + bill_gst),
                ("Net Payable", bill_net_due),
            ]
        else:
            bill_rows = [
                ("Total Interest Charged", total_int_due),
                ("GST @ 18%", bill_gst),
                ("Total Interest Payable", total_int_due + bill_gst),
            ]

        for label, value in bill_rows:
            pdf.cell(bill_widths[0], 8, label[:25], 1, 0, 'L')
            pdf.cell(bill_widths[1], 8, "", 1, 0)
            pdf.cell(bill_widths[2], 8, pdf_currency(value), 1, 1, 'R')

        # Transaction table for this bill
        pdf.ln(2)
        pdf.set_font("Arial", 'B', 7)
        pdf.set_fill_color(200, 200, 200)
        trans_widths = [20, 20, 30, 30, 12, 12, 30, 36]
        headers = ["Due Date", "Pay Date", "Op. Bal", "Paid", "Days", "ROI%", "Int", "Rem Bal"]

        for i, h in enumerate(headers):
            pdf.cell(trans_widths[i], 7, h, 1, 0, 'C', True)
        pdf.ln()

        pdf.set_font("Arial", '', 7)
        
        # Existing transactions
        for _, t in bill_trans.iterrows():
            pdf.cell(trans_widths[0], 7, str(bill['Due Date'])[:10], 1, 0, 'C')
            pdf.cell(trans_widths[1], 7, str(t['Date'])[:10], 1, 0, 'C')
            pdf.cell(trans_widths[2], 7, pdf_currency(t['Principal for Interest']), 1, 0, 'C')
            pdf.cell(trans_widths[3], 7, pdf_currency(t['Amount Paid']), 1, 0, 'C')
            pdf.cell(trans_widths[4], 7, str(t['Delayed Days']), 1, 0, 'C')
            pdf.cell(trans_widths[5], 7, f"{bill['Rate']}%", 1, 0, 'C')
            pdf.cell(trans_widths[6], 7, pdf_currency(t['Interest Charged']), 1, 0, 'C')
            pdf.cell(trans_widths[7], 7, pdf_currency(t['Remaining Balance']), 1, 1, 'C')

        # PENDING row for unpaid bills (red highlight)
        if bill['Status'] != 'Fully Paid':
            pdf.set_font("Arial", 'I', 7)
            pdf.set_fill_color(255, 240, 240)  # Light red background
            pdf.cell(trans_widths[0], 7, str(bill['Created_Date'])[:10], 1, 0, 'C', True)
            pdf.cell(trans_widths[1], 7, "PENDING", 1, 0, 'C', True)
            pdf.cell(trans_widths[2], 7, pdf_currency(bill['Balance']), 1, 0, 'C', True)
            pdf.cell(trans_widths[3], 7, "NA", 1, 0, 'C', True)
            pdf.cell(trans_widths[4], 7, str(days_overdue), 1, 0, 'C', True)
            pdf.cell(trans_widths[5], 7, f"{bill['Rate']}%", 1, 0, 'C', True)
            pdf.cell(trans_widths[6], 7, pdf_currency(live_int), 1, 0, 'C', True)
            pdf.cell(trans_widths[7], 7, pdf_currency(bill['Balance']), 1, 1, 'C', True)

        # Status statement
        pdf.ln(3)
        pdf.set_font("Arial", 'I', 8)
        if bill['Status'] != 'Fully Paid':
            statement = f"Bill is currently outstanding. Net payable: {pdf_currency(bill_net_due)}"
            pdf.set_text_color(200, 50, 50)  # Red text
        else:
            last_payment = bill_trans['Date'].max()
            last_date = last_payment.strftime('%d %b, %Y') if not pd.isna(last_payment) else "N/A"
            statement = f"Bill fully settled as of {last_date}"
            pdf.set_text_color(50, 150, 50)  # Green text
        
        pdf.cell(0, 6, statement, 0, 1)
        pdf.set_text_color(0, 0, 0)  # Reset to black

        pdf.ln(5)

    # Footer
    pdf.ln(8)
    pdf.set_font("Arial", 'I', 8)
    pdf.cell(0, 10, "This is a system-generated consolidated statement.", 0, 0, 'C')

    pdf_output = pdf.output(dest='S')
    return pdf_output if isinstance(pdf_output, bytes) else pdf_output.encode('latin-1', 'replace')

# --- UTILITY FUNCTIONS ---
def format_currency(value):
    return f"₹{value:,.2f}"

def load_uploaded_file(uploaded_file):
    if uploaded_file is not None:
        df = pd.read_excel(uploaded_file)
        date_cols = ['Due Date', 'Date', 'Created_Date']
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
        return df
    return pd.DataFrame()

def save_to_buffer(df, filename):
    output = io.BytesIO()
    df_save = df.copy()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_save.to_excel(writer, index=False)
    return output.getvalue()

# --- APP CONFIG ---
st.set_page_config(page_title="FinCalc Pro", page_icon="💰", layout="wide")

# --- SIDEBAR: FILE MANAGEMENT ---
st.sidebar.title("📁 File Management")

# Handle Bills Upload
bills_file = st.sidebar.file_uploader("Upload Bills", type=['xlsx'], key="bills_uploader")
if bills_file and not st.session_state.bills_processed:
    st.session_state.bills_df = load_uploaded_file(bills_file)
    st.session_state.bills_processed = True
    st.session_state.files_loaded = True

# Handle Trans Upload
trans_file = st.sidebar.file_uploader("Upload Transactions", type=['xlsx'], key="trans_uploader")
if trans_file and not st.session_state.trans_processed:
    st.session_state.trans_df = load_uploaded_file(trans_file)
    st.session_state.trans_processed = True

if st.sidebar.button("Reset / Clear All Data"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

st.sidebar.markdown("---")
menu = st.sidebar.radio("Navigation", ["Add New Bill", "Management Hub"])

# --- ADD NEW BILL ---
if menu == "Add New Bill":
    st.title("➕ Create New Invoice")
    
    with st.form("bill_form"):
        cust = st.text_input("Customer Name")
        bill_id_input = st.text_input("Bill ID (Optional)")
        amt = st.number_input("Invoice Amount", min_value=0.0, step=100.0)
        invoice_date = st.date_input("Billing Date", value=date.today())
        due = st.date_input("Due Date", value=date.today())
        rate = st.number_input("Interest Rate (%)", value=12.0)
        
        submitted = st.form_submit_button("Generate Bill")
        if submitted:
            if not cust or amt <= 0:
                st.error("Please provide a customer name and amount.")
            else:
                # ID Generation
                if not bill_id_input:
                    numeric_ids = [int(x) for x in st.session_state.bills_df['ID'] if str(x).isdigit()]
                    new_id = str(max(numeric_ids) + 1) if numeric_ids else "100001"
                else:
                    new_id = bill_id_input

                new_row = pd.DataFrame([{
                    'ID': new_id, 'Customer': cust, 'Original Amount': amt,
                    'Balance': amt, 'Due Date': due, 'Rate': rate,
                    'Status': 'Unpaid', 'Created_Date': invoice_date
                }])
                
                st.session_state.bills_df = pd.concat([st.session_state.bills_df, new_row], ignore_index=True)
                st.session_state.files_loaded = True
                st.success(f"Bill #{new_id} added successfully!")

# --- MANAGEMENT HUB ---
elif menu == "Management Hub":
    st.title("📊 Management Hub")
    
    if st.session_state.bills_df.empty:
        st.warning("No bills available. Please upload or add a bill.")
    else:
        # Use session state directly to ensure updates are visible
        bills = st.session_state.bills_df
        trans = st.session_state.trans_df
        
        customers = sorted(bills['Customer'].unique())
        selected_customer = st.selectbox("Select Customer", customers)
        
        cust_bills = bills[bills['Customer'] == selected_customer]
        cust_trans = trans[trans['Bill_ID'].isin(cust_bills['ID'])]

        # Summary Metrics
        total_outstanding = cust_bills['Balance'].sum()
        st.metric("Total Outstanding", format_currency(total_outstanding))

        # PDF Download
        stmt_date = st.date_input("Statement Date", value=date.today())
        pdf_bytes = create_customer_consolidated_pdf(selected_customer, stmt_date, cust_bills, cust_trans)
        st.download_button("📥 Download Statement (PDF)", pdf_bytes, "statement.pdf", "application/pdf")

        st.markdown("### Bill Details")
        for _, bill in cust_bills.iterrows():
            with st.expander(f"Bill #{bill['ID']} - {format_currency(bill['Balance'])}"):
                st.write(f"Due Date: {bill['Due Date']}")
                
                # Payment logic
                if bill['Status'] != 'Fully Paid':
                    p_amt = st.number_input("Payment Amount", min_value=0.0, key=f"pay_{bill['ID']}")
                    if st.button("Record Payment", key=f"btn_{bill['ID']}"):
                        # Update session state
                        idx = st.session_state.bills_df.index[st.session_state.bills_df['ID'] == bill['ID']][0]
                        new_bal = max(0, bill['Balance'] - p_amt)
                        st.session_state.bills_df.at[idx, 'Balance'] = new_bal
                        if new_bal == 0:
                            st.session_state.bills_df.at[idx, 'Status'] = 'Fully Paid'
                        
                        # Add transaction
                        new_t = pd.DataFrame([{
                            'Trans_ID': len(st.session_state.trans_df)+1, 'Bill_ID': bill['ID'],
                            'Date': date.today(), 'Amount Paid': p_amt, 'Interest Charged': 0,
                            'Remaining Balance': new_bal
                        }])
                        st.session_state.trans_df = pd.concat([st.session_state.trans_df, new_t], ignore_index=True)
                        st.rerun()