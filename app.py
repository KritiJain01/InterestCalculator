import streamlit as st
import pandas as pd
import io
from datetime import date
from fpdf import FPDF
import tempfile

# --- SESSION STATE FOR FILE MANAGEMENT ---
if 'bills_file' not in st.session_state:
    st.session_state.bills_file = None
if 'trans_file' not in st.session_state:
    st.session_state.trans_file = None
if 'bills_df' not in st.session_state:
    st.session_state.bills_df = pd.DataFrame()
if 'trans_df' not in st.session_state:
    st.session_state.trans_df = pd.DataFrame()

# --- PDF GENERATION FUNCTIONS (unchanged) ---
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


# --- FILE UPLOAD & DOWNLOAD FUNCTIONS ---
def format_currency(value):
    return f"₹{value:,.2f}"

def load_uploaded_file(uploaded_file):
    """Load data from uploaded Excel file"""
    if uploaded_file is not None:
        df = pd.read_excel(uploaded_file)
        date_cols = ['Due Date', 'Date', 'Created_Date']
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
        return df
    return pd.DataFrame()

def save_to_buffer(df, filename):
    """Save DataFrame to BytesIO buffer for download"""
    output = io.BytesIO()
    date_cols = ['Due Date', 'Date', 'Created_Date']
    df_save = df.copy()
    for col in date_cols:
        if col in df_save.columns:
            df_save[col] = pd.to_datetime(df_save[col], errors='coerce').dt.date
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_save.to_excel(writer, sheet_name=filename.split('.')[0][:31], index=False)
    output.seek(0)
    return output.getvalue()

# --- APP INTERFACE ---
st.set_page_config(page_title="FinCalc Pro | Management Hub", page_icon="💰", layout="wide")

st.sidebar.title("📁 File Management")
st.sidebar.markdown("**Upload your Excel files**")

# FILE UPLOAD SECTION
bills_upload = st.sidebar.file_uploader("Upload Bills Excel", type=['xlsx', 'xls'], key="bills_upload")
trans_upload = st.sidebar.file_uploader("Upload Transactions Excel", type=['xlsx', 'xls'], key="trans_upload")

# Update session state when files are uploaded
if bills_upload is not None:
    st.session_state.bills_file = bills_upload
    st.session_state.bills_df = load_uploaded_file(bills_upload)
    st.success("✅ Bills file loaded!")

if trans_upload is not None:
    st.session_state.trans_file = trans_upload
    st.session_state.trans_df = load_uploaded_file(trans_upload)
    st.success("✅ Transactions file loaded!")

# DOWNLOAD BUTTONS
if not st.session_state.bills_df.empty:
    st.sidebar.download_button(
        "⬇️ Download Updated Bills.xlsx",
        data=save_to_buffer(st.session_state.bills_df, "Bills.xlsx"),
        file_name="Bills.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if not st.session_state.trans_df.empty:
    st.sidebar.download_button(
        "⬇️ Download Updated Transactions.xlsx",
        data=save_to_buffer(st.session_state.trans_df, "Transactions.xlsx"),
        file_name="Transactions.xlsx", 
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

st.sidebar.markdown("---")
menu = st.sidebar.radio("Navigation", ["Add New Bill", "Management Hub"])

# MAIN APP LOGIC (modified to use session state dataframes)
if menu == "Add New Bill":
    st.title("Create New Invoice")
    
    # Check if files are loaded
    if st.session_state.bills_df.empty:
        st.warning("⚠️ Please upload Bills Excel file first!")
        st.stop()
    
    with st.form("bill_form"):
        cust = st.text_input("Customer Name")
        bill_id_input = st.text_input("Bill ID (Optional - leave empty for auto-generate)", 
                                    help="Leave empty for auto: 100001, 100002... or enter custom: DL234252324")
        amt = st.number_input("Invoice Amount", min_value=0.0, step=0.01)
        invoice_date = st.date_input("Billing Date", value=date.today())
        due = st.date_input("Due Date", value=date.today())
        rate = st.number_input("Annual Interest Rate (%)", value=12.0, min_value=0.0)
        
        submitted = st.form_submit_button("Generate Bill", use_container_width=True)
        if submitted:
            if cust and amt > 0:
                bills = st.session_state.bills_df.copy()
                
                if not bill_id_input or str(bill_id_input).strip() == "":
                    # ✅ AUTO-GENERATE: Works with mixed alphanumeric IDs
                    if not bills.empty:
                        numeric_ids = []
                        for id_val in bills['ID']:
                            if str(id_val).isdigit():
                                numeric_ids.append(int(id_val))
                        new_id = str(max(numeric_ids) + 1) if numeric_ids else "100001"
                    else:
                        new_id = "100001"
                else:
                    new_id = str(bill_id_input).strip()
                
                # Check duplicate
                if new_id in bills['ID'].astype(str).values:
                    st.error("❌ Bill ID already exists!")
                else:
                    new_bill = pd.DataFrame({
                        'ID': [new_id], 'Customer': [cust], 'Original Amount': [amt],
                        'Balance': [amt], 'Due Date': [due], 'Rate': [rate],
                        'Status': ['Unpaid'], 'Created_Date': [invoice_date]
                    })
                    st.session_state.bills_df = pd.concat([bills, new_bill], ignore_index=True)
                    st.success(f"✅ Bill #{new_id} created successfully!")
                    st.rerun()
            else:
                st.error("Please provide valid Customer name and Amount.")

elif menu == "Management Hub":
    st.title("Customer Management Hub")
    
    # Check if files are loaded
    if st.session_state.bills_df.empty:
        st.warning("⚠️ **Please upload Bills Excel file first from the sidebar!**")
        st.stop()
    
    bills = st.session_state.bills_df.copy()
    trans = st.session_state.trans_df.copy()
    
    if bills.empty:
        st.info("No bills found. Add some bills first!")
        st.stop()

    # Customer Selection
    st.markdown("### Select Customer")
    customers = sorted(bills['Customer'].unique())
    selected_customer = st.selectbox("Choose Customer", customers)
    
    cust_bills = bills[bills['Customer'] == selected_customer].copy()
    cust_trans = trans[trans['Bill_ID'].isin(cust_bills['ID'])].copy()

    if cust_bills.empty:
        st.warning("No bills found for this customer.")
        st.stop()

    # Consolidated Summary (same logic)
    st.markdown("### Consolidated Summary")
    today = date.today()
    
    total_original = cust_bills['Original Amount'].sum()
    total_balance = cust_bills['Balance'].sum()
    total_live_interest = 0
    
    for _, b in cust_bills.iterrows():
        days = max(0, (today - b['Due Date']).days)
        live_int = (b['Balance'] * b['Rate'] / 100 * days) / 365
        past_int = cust_trans[cust_trans['Bill_ID'] == b['ID']]['Interest Charged'].sum()
        total_live_interest += past_int
    
    gst = total_live_interest * 0.18
    net_due = total_balance + total_live_interest + gst

    # Metrics display (same)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Billed Amount", format_currency(total_original))
    with col2:
        st.metric("Outstanding Principal", format_currency(total_balance))

    st.markdown("---")

    col4, col5, col6 = st.columns(3)
    with col4:
        st.metric("Interest (for Amount Paid)", format_currency(total_live_interest))
    with col5:
        st.metric("GST @18%", format_currency(gst))
    with col6:
        st.metric("Net Payable Interest", format_currency(total_live_interest+gst))

    # PDF Download (same)
    st.markdown("---")
    stmt_date = st.date_input("Statement Date for PDF", value=today)
    pdf_data = create_customer_consolidated_pdf(selected_customer, stmt_date, cust_bills, cust_trans)
    st.download_button(
        "📥 Download Consolidated PDF",
        data=pdf_data,
        file_name=f"{selected_customer}_Consolidated_{stmt_date.strftime('%Y%m%d')}.pdf",
        mime="application/pdf",
        use_container_width=True
    )

    # Individual Bills section (modified to update session state)
    st.divider()
    st.markdown("### All Bills for Customer")
    
    for idx, bill in cust_bills.iterrows():
        with st.expander(f"Bill #{bill['ID']} | {bill['Status']} | Balance: {format_currency(bill['Balance'])}", expanded=False):
            # Bill details (same)
            due_date = bill['Due Date']
            days_overdue = max(0, (today - due_date).days)
            live_interest = (bill['Balance'] * bill['Rate']/100 * days_overdue) / 365
            
            col1, col2, col3, col4, col5, col6 = st.columns(6)
            with col1:
                st.metric("Billed Amount", format_currency(bill['Original Amount']))
            with col2:
                st.metric("Billing Date", bill['Created_Date'].strftime('%d %b, %Y'))
            with col3:
                st.metric("Due Date", due_date.strftime('%d %b, %Y'))
            with col4:
                st.metric("Balance Left", format_currency(bill['Balance']))
            with col5:
                st.metric("ROI", f"{bill['Rate']}%")
            with col6:
                st.metric("Total Interest", format_currency(live_interest))

            # Transaction history (same display logic)
            bill_trans = cust_trans[cust_trans['Bill_ID'] == bill['ID']].copy()
            if not bill_trans.empty:
                st.subheader("Transaction History")
                disp_table = bill_trans.copy()
                disp_table['Billing Date'] = bill['Created_Date']
                disp_table['ROI%'] = f"{bill['Rate']}%"
                for col in ['Principal for Interest', 'Interest Charged', 'Amount Paid', 'Remaining Balance']:
                    disp_table[col] = disp_table[col].apply(format_currency)
                disp_table = disp_table.rename(columns={
                    'Date': 'Payment Date', 
                    'Principal for Interest': 'Opening Balance'
                })
                final_cols = ['Billing Date', 'Payment Date', 'Opening Balance', 'Amount Paid', 
                            'Delayed Days', 'ROI%', 'Interest Charged', 'Remaining Balance']
                st.dataframe(disp_table[final_cols], use_container_width=True, hide_index=True)

            # DELETE BILL (updates session state)
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown("**Delete this entire bill?**")
            with col2:
                if st.button(f"🗑️ Delete Bill #{bill['ID']}", type="secondary", use_container_width=True, key=f"del_{bill['ID']}"):
                    st.session_state.bills_df = st.session_state.bills_df[st.session_state.bills_df['ID'] != bill['ID']]
                    st.session_state.trans_df = st.session_state.trans_df[st.session_state.trans_df['Bill_ID'] != bill['ID']]
                    st.success(f"✅ Bill #{bill['ID']} deleted!")
                    st.rerun()

            # Payment form (updates session state)
            if bill['Status'] != 'Fully Paid':
                st.markdown("---")
                st.subheader("💰 Record New Payment")
                p_date = st.date_input("Payment Date", value=today, key=f"pdate_{bill['ID']}")
                p_amt = st.number_input("Amount Paid", min_value=0.0, step=0.01, key=f"pamt_{bill['ID']}")
                
                days_late = max(0, (p_date - due_date).days)
                interest_charge = (min(p_amt, bill['Balance']) * (bill['Rate']/100) * days_late) / 365
                max_payable = bill['Balance'] + interest_charge
                
                col1, col2 = st.columns(2)
                with col1:
                    st.info(f"Interest to charge: {format_currency(interest_charge)}")
                with col2:
                    st.info(f"Max payable: {format_currency(max_payable)}")
                
                if st.button(f"✅ Record Payment", 
                           disabled=(p_amt <= 0 or p_amt > max_payable + 1), 
                           use_container_width=True,
                           key=f"paybtn_{bill['ID']}"):
                    bills = st.session_state.bills_df.copy()
                    trans = st.session_state.trans_df.copy()
                    
                    opening_principal = bill['Balance']
                    new_balance = max(0, opening_principal - p_amt)
                    
                    new_t_id = int(trans['Trans_ID'].max() + 1) if not trans.empty else 1
                    new_entry = pd.DataFrame([{
                        'Trans_ID': new_t_id, 'Bill_ID': bill['ID'], 'Date': p_date,
                        'Principal for Interest': opening_principal, 'Delayed Days': days_late,
                        'Interest Charged': interest_charge, 'Amount Paid': p_amt,
                        'Remaining Balance': new_balance
                    }])
                    
                    # Update bills dataframe
                    bills.loc[bills['ID'] == bill['ID'], 'Balance'] = new_balance
                    if new_balance <= 99.99:
                        bills.loc[bills['ID'] == bill['ID'], 'Status'] = 'Fully Paid'
                        bills.loc[bills['ID'] == bill['ID'], 'Balance'] = 0
                    
                    # Update session state
                    st.session_state.bills_df = bills
                    st.session_state.trans_df = pd.concat([trans, new_entry], ignore_index=True)
                    st.success("✅ Payment recorded successfully!")
                    st.rerun()
            else:
                st.success("✅ This bill is fully paid.")
