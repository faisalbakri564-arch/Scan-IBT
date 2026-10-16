import streamlit as st
import pandas as pd
import pdfplumber
import re
import io
import gspread
from google.oauth2.service_account import Credentials

# Mengatur tampilan halaman web
st.set_page_config(page_title="Receiving IBT System", layout="wide", page_icon="📦")

# --- KONEKSI KE GOOGLE SHEETS (Metode Aman & Stabil) ---
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1oECCwC3p9544FaPefpscAAs5hsVxqN8wcxhlt54hpkA/edit"

@st.cache_resource
def setup_gsheets():
    try:
        # Mengambil kredensial langsung dari toml secrets Streamlit
        creds_dict = dict(st.secrets["gcp_service_account"])
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_url(SPREADSHEET_URL).sheet1
        return sheet
    except Exception as e:
        st.error(f"⚠️ Detail Error Koneksi Google Sheets: {e}")
        return None

sheet = setup_gsheets()

# --- FUNGSI BACA DATA ---
def get_data_from_sheets():
    if sheet is None: return pd.DataFrame()
    try:
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()

def baca_pdf_ibt_multi(file_pdf):
    data_barang = []
    metadata = {"IBT No": "-", "ERP No": "-"}
    with pdfplumber.open(file_pdf) as pdf:
        for halaman in pdf.pages:
            teks = halaman.extract_text()
            match_ibt = re.search(r'IBT No\.:\s*(\S+)', teks)
            if match_ibt: metadata["IBT No"] = match_ibt.group(1)
            match_erp = re.search(r'ERP No\.:\s*([\d,]+)', teks)
            if match_erp: metadata["ERP No"] = match_erp.group(1)
            
            baris_teks = teks.split("\n")
            for baris in baris_teks:
                cocok = re.search(r'(\d{13})\s+(.*?)\s+EA\s+(\d+)\s+(\d+)', baris)
                if cocok:
                    data_barang.append([
                        metadata["IBT No"],
                        metadata["ERP No"],
                        cocok.group(1),
                        cocok.group(2).strip(),
                        int(cocok.group(4)),
                        0,
                        "Belum Dicek"
                    ])
    return data_barang

# ==========================================
# PEMISAHAN HALAMAN ADMIN vs STAFF
# ==========================================
if 'role' not in st.session_state:
    st.session_state['role'] = None

if sheet is None:
    st.error("Gagal terhubung ke Google Sheets. Silakan periksa kembali format 'Secrets' di pengaturan Streamlit Anda.")
    st.stop()

if st.session_state['role'] is None:
    st.title("📦 Sistem Receiving IBT Guardian")
    st.write("Silakan pilih peran Anda untuk masuk ke sistem:")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💻 Masuk sebagai Admin (PC)", use_container_width=True):
            st.session_state['role'] = "Admin"
            st.rerun()
    with col2:
        if st.button("📱 Masuk sebagai Staff (HP)", use_container_width=True):
            st.session_state['role'] = "Staff"
            st.rerun()

# ==========================================
# HALAMAN ADMIN (Hanya Tampil di PC)
# ==========================================
elif st.session_state['role'] == "Admin":
    st.title("💻 Dashboard Admin IBT")
    if st.button("⬅️ Kembali ke Menu Awal"):
        st.session_state['role'] = None
        st.rerun()
        
    tab1, tab3 = st.tabs(["📥 1. Upload Data PDF", "📝 2. Laporan & Edit Excel"])
    
    with tab1:
        st.header("Upload File IBT")
        file_uploads = st.file_uploader("Upload File PDF IBT (Maks 10 file)", type=["pdf"], accept_multiple_files=True)

        if st.button("Proses Upload ke Database"):
            if file_uploads:
                with st.spinner("Mengunggah data ke Google Sheets..."):
                    semua_data = []
                    for file in file_uploads:
                        semua_data.extend(baca_pdf_ibt_multi(file))
                    if semua_data:
                        sheet.clear()
                        sheet.append_row(["IBT No", "ERP No", "Barcode", "Nama Barang", "Target IBT", "Hasil Cek Store", "Status"])
                        sheet.append_rows(semua_data)
                        st.success("✅ Data berhasil diunggah dan disinkronkan ke Cloud!")
            else:
                st.warning("Pilih file PDF dulu!")
                
        st.markdown("---")
        st.write("Data Saat Ini di Database Google Sheets:")
        st.dataframe(get_data_from_sheets(), use_container_width=True)

    with tab3:
        st.header("Koreksi & Download Laporan Akhir")
        df_akhir = get_data_from_sheets()
        if not df_akhir.empty:
            df_edit = st.data_editor(df_akhir, num_rows="dynamic", use_container_width=True)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_edit.to_excel(writer, index=False, sheet_name='Laporan_Receiving')
            st.download_button(
                label="📊 Download Laporan (Excel)",
                data=output.getvalue(),
                file_name='Hasil_Receiving_Akhir.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )
        else:
            st.info("Belum ada data di database.")

# ==========================================
# HALAMAN STAFF (Hanya Tampil di HP)
# ==========================================
elif st.session_state['role'] == "Staff":
    st.title("📱 Pengecekan Barang")
    if st.button("⬅️ Ganti Peran"):
        st.session_state['role'] = None
        st.rerun()
        
    df_sementara = get_data_from_sheets()
    
    if not df_sementara.empty and 'IBT No' in df_sementara.columns:
        daftar_ibt = df_sementara['IBT No'].unique()
        pilih_ibt = st.selectbox("📌 Pilih dokumen IBT yang kamu bongkar:", daftar_ibt)
        st.markdown("---")
        
        st.write("📷 **Foto Barcode Kardus (Opsional)**")
        foto = st.camera_input("Jepret Kamera")
        if foto:
            st.success("Foto berhasil diambil!")
            
        st.markdown("---")
        st.write("📦 **Input Barang ke Database**")
        with st.form(key='form_scan', clear_on_submit=True):
            barcode_manual = st.text_input("Ketik 13 Digit Barcode:", placeholder="Misal: 9555237206059")
            qty_input = st.number_input("Jumlah (Qty):", min_value=1, value=1, step=1)
            submit_scan = st.form_submit_button("➕ Simpan Data", use_container_width=True)

        if submit_scan and barcode_manual:
            barcode_manual = barcode_manual.strip()
            df_terbaru = get_data_from_sheets()
            
            kondisi_ibt = df_terbaru['IBT No'] == pilih_ibt
            kondisi_barcode = df_terbaru['Barcode'].astype(str) == barcode_manual
            pencarian = df_terbaru[kondisi_ibt & kondisi_barcode]
            
            if not pencarian.empty:
                idx = pencarian.index[0]
                target = int(df_terbaru.at[idx, 'Target IBT'])
                hasil_lama = int(df_terbaru.at[idx, 'Hasil Cek Store'])
                hasil_baru = hasil_lama + qty_input
                status_baru = "✅ Sesuai" if hasil_baru == target else ("⚠️ Over-receive" if hasil_baru > target else "⏳ Kurang")
                
                row_in_sheet = int(idx) + 2 
                sheet.update_cell(row_in_sheet, 6, hasil_baru)
                sheet.update_cell(row_in_sheet, 7, status_baru)
                
                st.success(f"Berhasil! {qty_input} pcs {df_terbaru.at[idx, 'Nama Barang']} ditambahkan.")
            else:
                st.error(f"❌ Barcode {barcode_manual} TIDAK ADA dalam IBT {pilih_ibt}!")
    else:
        st.warning("⚠️ Database masih kosong. Minta Admin untuk meng-upload file PDF terlebih dahulu di komputer.")
