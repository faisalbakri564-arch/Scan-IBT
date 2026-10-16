import streamlit as st
import pandas as pd
import pdfplumber
import re
import io

# Mengatur tampilan halaman web
st.set_page_config(page_title="Dashboard Receiving IBT", layout="wide", page_icon="📦")

# --- SIDEBAR (FITUR REFRESH) ---
with st.sidebar:
    st.header("⚙️ Menu Sistem")
    st.write("Klik tombol di bawah jika ingin mengosongkan aplikasi.")
    if st.button("🔄 Refresh / Hapus Semua Data", use_container_width=True):
        st.session_state.clear()
        st.rerun()

st.title("📦 Dashboard Receiving IBT (Multi-File)")

# Fungsi untuk membaca PDF (sedikit dimodifikasi untuk membaca banyak file)
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

# --- MEMBUAT TAMPILAN DASHBOARD (3 TAB) ---
tab1, tab2, tab3 = st.tabs(["📥 1. Upload Data IBT", "📇 2. Input Scan Barang", "📝 3. Laporan Akhir"])

# ==========================================
# TAB 1: UPLOAD BANYAK DATA (MAX 10)
# ==========================================
with tab1:
    st.header("Upload File IBT")
    st.write("Bisa langsung pilih banyak file PDF sekaligus (maks 10 file).")

    # PERUBAHAN: accept_multiple_files=True
    file_uploads = st.file_uploader("Upload File PDF IBT di sini", type=["pdf"], accept_multiple_files=True)

    if file_uploads:
        if 'data_ibt' not in st.session_state:
            semua_data = [] # Menampung sementara semua tabel

            for file in file_uploads:
                df_hasil = baca_pdf_ibt_multi(file)
                semua_data.append(df_hasil)

            # Menggabungkan semua tabel PDF menjadi 1 Master Tabel
            df_master = pd.concat(semua_data, ignore_index=True)
            st.session_state['data_ibt'] = df_master

        st.success(f"✅ Berhasil membaca {len(file_uploads)} file IBT!")
        st.dataframe(st.session_state['data_ibt'], use_container_width=True)

# ==========================================
# TAB 2: SCAN BARANG (Berdasarkan No IBT)
# ==========================================
with tab2:
    st.header("Pengecekan Barang")

    if 'data_ibt' in st.session_state:
        df_sementara = st.session_state['data_ibt']
        daftar_ibt = df_sementara['IBT No'].unique() # Daftar IBT yang sudah diupload

        # 1. Kotak Scan Nomor IBT (Menggantikan Dropdown)
        st.write("📌 **Langkah 1: Buka Dokumen**")
        pilih_ibt = st.text_input("📄 Scan Barcode No. IBT pada kertas:", placeholder="Arahkan scanner ke barcode IBT...")

        # Jika ada nomor IBT yang discan/diketik
        if pilih_ibt:
            pilih_ibt = pilih_ibt.strip() # Menghilangkan spasi tidak sengaja

            # Cek apakah IBT yang discan ada di data yang diupload Admin
            if pilih_ibt in daftar_ibt:
                st.success(f"✅ Dokumen IBT **{pilih_ibt}** aktif! Silakan lanjut scan barang di bawah.")
                st.markdown("---")

                # 2. Form Input Scan Barang (Hanya muncul kalau IBT-nya benar)
                st.write("📌 **Langkah 2: Scan Fisik Barang**")
                with st.form(key='form_scan', clear_on_submit=True):
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        barcode_scan = st.text_input("🔫 Scan/Ketik Barcode Barang:", placeholder="13 digit barcode...")
                    with col2:
                        qty_input = st.number_input("📦 Jumlah (Qty):", min_value=1, value=1, step=1)
                    with col3:
                        st.write("")
                        st.write("")
                        submit_scan = st.form_submit_button("➕ Simpan Data", use_container_width=True)

                if submit_scan and barcode_scan:
                    barcode_scan = barcode_scan.strip()

                    kondisi_ibt = df_sementara['IBT No'] == pilih_ibt
                    kondisi_barcode = df_sementara['Barcode'] == barcode_scan

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
                        st.error(f"❌ Barcode {barcode_scan} TIDAK ADA dalam dokumen IBT {pilih_ibt}!")

                    st.session_state['data_ibt'] = df_sementara
            else:
                st.error(f"❌ Nomor IBT '{pilih_ibt}' belum di-upload oleh Admin di Tab 1!")

    else:
        st.warning("⚠️ Silakan upload file PDF IBT di Tab 1 terlebih dahulu!")
# ==========================================
# TAB 3: EDIT HASIL & DOWNLOAD EXCEL
# ==========================================
with tab3:
    st.header("Koreksi Data & Download Laporan")

    if 'data_ibt' in st.session_state:
        df_edit = st.data_editor(st.session_state['data_ibt'], num_rows="dynamic", use_container_width=True)
        st.session_state['data_ibt'] = df_edit

        st.markdown("---")

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_edit.to_excel(writer, index=False, sheet_name='Laporan_Receiving')

        excel_data = output.getvalue()

        st.download_button(
            label="📊 Download Laporan (Excel Rapi)",
            data=excel_data,
            file_name=f'Hasil_Receiving_Gabungan.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
    else:
        st.warning("⚠️ Belum ada data. Silakan upload file PDF terlebih dahulu.")