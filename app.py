import streamlit as st
import pandas as pd
import pdfplumber
import re
import io
from streamlit_qrcode_scanner import qrcode_scanner

# Mengatur tampilan halaman web
st.set_page_config(page_title="Dashboard Receiving IBT", layout="wide", page_icon="📦")

with st.sidebar:
    st.header("⚙️ Menu Sistem")
    st.write("Klik tombol di bawah jika ingin mengosongkan aplikasi.")
    if st.button("🔄 Refresh / Hapus Semua Data", use_container_width=True):
        st.session_state.clear()
        st.rerun()

st.title("📦 Dashboard Receiving IBT (Kamera HP)")

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
                    barcode = cocok.group(1)
                    nama_barang = cocok.group(2).strip()
                    qty_target = int(cocok.group(4))
                    
                    data_barang.append({
                        "IBT No": metadata["IBT No"],
                        "ERP No": metadata["ERP No"],
                        "Barcode": barcode,
                        "Nama Barang": nama_barang,
                        "Target IBT": qty_target,
                        "Hasil Cek Store": 0,
                        "Status": "Belum Dicek"
                    })
    return pd.DataFrame(data_barang)

tab1, tab2, tab3 = st.tabs(["📥 1. Upload Data IBT", "📇 2. Input Scan Barang", "📝 3. Laporan Akhir"])

# ==========================================
# TAB 1: UPLOAD DATA
# ==========================================
with tab1:
    st.header("Upload File IBT")
    file_uploads = st.file_uploader("Upload File PDF IBT di sini (Maks 10 file)", type=["pdf"], accept_multiple_files=True)

    if file_uploads:
        if 'data_ibt' not in st.session_state:
            semua_data = []
            for file in file_uploads:
                semua_data.append(baca_pdf_ibt_multi(file))
            st.session_state['data_ibt'] = pd.concat(semua_data, ignore_index=True)
        st.success(f"✅ Berhasil membaca {len(file_uploads)} file IBT!")
        st.dataframe(st.session_state['data_ibt'], use_container_width=True)

# ==========================================
# TAB 2: SCAN BARANG DENGAN KAMERA HP
# ==========================================
with tab2:
    st.header("Pengecekan Barang via Kamera")
    
    if 'data_ibt' in st.session_state:
        df_sementara = st.session_state['data_ibt']
        daftar_ibt = df_sementara['IBT No'].unique()
        
        st.write("📌 **Langkah 1: Pilih Nomor IBT**")
        pilih_ibt = st.selectbox("Pilih dokumen yang sedang dikerjakan:", daftar_ibt)
        
        st.markdown("---")
        st.write("📌 **Langkah 2: Scan Fisik Barang**")
        st.write("Arahkan kamera ke barcode barang. Sistem akan otomatis mendeteksinya.")
        
        # INI FITUR KAMERANYA
        kamera_scan = qrcode_scanner(key='kamera_scanner')
        
        # Opsi manual jika kamera HP tidak fokus
        st.write("Atau ketik manual:")
        barcode_manual = st.text_input("Ketik 13 digit barcode:", placeholder="Ketik lalu tekan enter...")
        
        qty_input = st.number_input("📦 Jumlah (Qty) jika barangnya sama:", min_value=1, value=1, step=1)
        
        # Deteksi barcode (bisa dari kamera atau ketik manual)
        barcode_akhir = kamera_scan if kamera_scan else barcode_manual

        if barcode_akhir:
            barcode_akhir = barcode_akhir.strip()
            
            kondisi_ibt = df_sementara['IBT No'] == pilih_ibt
            kondisi_barcode = df_sementara['Barcode'] == barcode_akhir
            pencarian = df_sementara[kondisi_ibt & kondisi_barcode]
            
            if not pencarian.empty:
                idx = pencarian.index[0]
                df_sementara.at[idx, 'Hasil Cek Store'] += qty_input
                
                target = df_sementara.at[idx, 'Target IBT']
                hasil = df_sementara.at[idx, 'Hasil Cek Store']
                
                if hasil == target:
                    df_sementara.at[idx, 'Status'] = "✅ Sesuai"
                elif hasil > target:
                    df_sementara.at[idx, 'Status'] = "⚠️ Over-receive"
                else:
                    df_sementara.at[idx, 'Status'] = "⏳ Kurang"
                    
                st.success(f"Berhasil! {qty_input} pcs {df_sementara.at[idx, 'Nama Barang']} masuk ke IBT {pilih_ibt}.")
            else:
                st.error(f"❌ Barcode {barcode_akhir} TIDAK ADA dalam IBT {pilih_ibt}!")
            
            st.session_state['data_ibt'] = df_sementara

    else:
        st.warning("⚠️ Silakan upload file PDF IBT di Tab 1 terlebih dahulu!")

# ==========================================
# TAB 3: Laporan Akhir
# ==========================================
with tab3:
    st.header("Koreksi & Download")
    if 'data_ibt' in st.session_state:
        df_edit = st.data_editor(st.session_state['data_ibt'], num_rows="dynamic", use_container_width=True)
        st.session_state['data_ibt'] = df_edit
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_edit.to_excel(writer, index=False, sheet_name='Laporan_Receiving')
        
        st.download_button(
            label="📊 Download Laporan (Excel Rapi)",
            data=output.getvalue(),
            file_name=f'Hasil_Receiving_Gabungan.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
    else:
        st.warning("⚠️ Belum ada data. Silakan upload file PDF terlebih dahulu.")
