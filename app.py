import streamlit as st
import pandas as pd
import pdfplumber
import re
import io
import os
import streamlit.components.v1 as components

# Mengatur tampilan halaman web
st.set_page_config(page_title="Receiving IBT System", layout="wide", page_icon="📦")

DB_FILE = "database_lokal.json"

# --- FUNGSI DATABASE LOKAL & HAPUS DATA ---
def load_data():
    if os.path.exists(DB_FILE):
        try:
            return pd.read_json(DB_FILE)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()

def save_data(df):
    df.to_json(DB_FILE, orient="records", indent=4)

def hapus_semua_data():
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

# --- MENU SAMPING (SIDEBAR) UNTUK HAPUS DATA ---
with st.sidebar:
    st.header("⚙️ Pengaturan Sistem")
    st.write("Gunakan tombol ini untuk mereset aplikasi dan menghapus data yang tersimpan agar tidak ada jejak.")
    if st.button("🗑️ Hapus Seluruh Data Sistem", type="primary", use_container_width=True):
        hapus_semua_data()
        st.session_state['role'] = None
        st.success("✅ Seluruh data berhasil dihapus dari sistem!")
        import time
        time.sleep(1)
        st.rerun()

# --- FUNGSI BACA PDF (DISESUAIKAN DENGAN TABEL IBT) ---
def baca_pdf_ibt_multi(file_pdf):
    data_barang = []
    metadata = {"IBT No": "-"}
    with pdfplumber.open(file_pdf) as pdf:
        for halaman in pdf.pages:
            teks = halaman.extract_text()
            
            # Cari Nomor IBT
            match_ibt = re.search(r'IBT No\.:\s*(\S+)', teks)
            if match_ibt: metadata["IBT No"] = match_ibt.group(1)
            
            baris_teks = teks.split("\n")
            for baris in baris_teks:
                # Pola Tabel: [No] [Sub Category] [Item Code (6-7 digit)] [Barcode (12-13 digit)] [Item Name...]
                # Contoh baris: 2 101010|DERMA... 3124761 3337875829007 CERAVE...
                cocok = re.search(r'\d+\s+.*?\s+(\d{6,7})\s+(\d{12,13})\s+(.*?)(?=\s+Total:|\s*$)', baris)
                
                if cocok:
                    item_code = cocok.group(1)
                    barcode = cocok.group(2)
                    nama_barang = cocok.group(3).strip()
                    
                    data_barang.append({
                        "IBT No": metadata["IBT No"],
                        "Barcode": barcode,
                        "PLU / Item Code": item_code,
                        "Nama Barang": nama_barang,
                        "Target IBT": 1, # Default kuantitas baris tabel IBT Guardian
                        "Hasil Cek Store": 0,
                        "Status": "Belum Dicek"
                    })
                else:
                    # Pola Alternatif jika format teks menyatu
                    # Mencari angka Item Code (6-7 digit) diikuti Barcode (12-13 digit)
                    cocok_alt = re.search(r'(\d{6,7})\s+(\d{12,13})\s+(.*)', baris)
                    if cocok_alt:
                        item_code = cocok_alt.group(1)
                        barcode = cocok_alt.group(2)
                        sisa_teks = cocok_alt.group(3).strip()
                        
                        data_barang.append({
                            "IBT No": metadata["IBT No"],
                            "Barcode": barcode,
                            "PLU / Item Code": item_code,
                            "Nama Barang": sisa_teks,
                            "Target IBT": 1,
                            "Hasil Cek Store": 0,
                            "Status": "Belum Dicek"
                        })
                        
    return pd.DataFrame(data_barang)

# ==========================================
# PEMISAHAN HALAMAN ADMIN vs STAFF
# ==========================================
if 'role' not in st.session_state:
    st.session_state['role'] = None

if st.session_state['role'] is None:
    st.title("📦 Sistem Receiving IBT Guardian")
    st.write("Silakan pilih peran Anda:")
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
# HALAMAN ADMIN (PC)
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
                semua_df = []
                for file in file_uploads:
                    semua_df.append(baca_pdf_ibt_multi(file))
                if semua_df:
                    df_gabung = pd.concat(semua_df, ignore_index=True)
                    save_data(df_gabung)
                    st.success("✅ Data berhasil disimpan di server lokal! Staf HP sudah bisa mengecek.")
            else:
                st.warning("Pilih file PDF dulu!")
                
        st.markdown("---")
        
        col_live1, col_live2 = st.columns([8, 2])
        with col_live1:
            st.write("Data Saat Ini di Database:")
        with col_live2:
            if st.button("🔄 Muat Ulang Scanner", use_container_width=True):
                st.rerun()
                
        st.dataframe(load_data(), use_container_width=True)

    with tab3:
        st.header("Koreksi & Download Laporan Akhir")
        df_curr = load_data()
        
        if not df_curr.empty and 'IBT No' in df_curr.columns:
            daftar_ibt = ["Semua IBT"] + list(df_curr['IBT No'].unique())
            pilih_ibt_admin = st.selectbox("📌 Pilih dokumen IBT yang ingin diproses/didownload:", daftar_ibt)
            
            if pilih_ibt_admin == "Semua IBT":
                df_filter = df_curr
            else:
                df_filter = df_curr[df_curr['IBT No'] == pilih_ibt_admin]
                
            st.markdown("---")
            
            if st.button(f"🔄 Tarik Data Scan Terbaru untuk {pilih_ibt_admin}"):
                st.rerun()

            st.write("Silakan koreksi jumlah Qty jika ada selisih sebelum mendownload:")
            
            df_edit = st.data_editor(df_filter, use_container_width=True)
            
            df_curr.update(df_edit)
            save_data(df_curr)
            
            st.markdown("---")
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_edit.to_excel(writer, index=False, sheet_name='Laporan_Receiving')
            
            nama_file = 'Hasil_Receiving_Semua.xlsx' if pilih_ibt_admin == "Semua IBT" else f'Hasil_Receiving_{pilih_ibt_admin}.xlsx'
            
            st.download_button(
                label=f"📊 Download Laporan ({pilih_ibt_admin})",
                data=output.getvalue(),
                file_name=nama_file,
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                type="primary"
            )
        else:
            st.info("Belum ada data.")

# ==========================================
# HALAMAN STAFF (HP)
# ==========================================
elif st.session_state['role'] == "Staff":
    st.title("📱 Pengecekan Barang")
    if st.button("⬅️ Ganti Peran"):
        st.session_state['role'] = None
        st.rerun()
        
    df_data = load_data()
    
    if not df_data.empty and 'IBT No' in df_data.columns:
        daftar_ibt = df_data['IBT No'].unique()
        pilih_ibt = st.selectbox("📌 Pilih dokumen IBT yang kamu bongkar:", daftar_ibt)
        st.markdown("---")
        
        st.write("📷 **Kamera Scanner (Opsional)**")
        
        if "tampilkan_scanner" not in st.session_state:
            st.session_state["tampilkan_scanner"] = False
            
        if not st.session_state["tampilkan_scanner"]:
            if st.button("📸 Hidupkan Scanner Kamera", type="primary"):
                st.session_state["tampilkan_scanner"] = True
                st.rerun()
        else:
            if st.button("❌ Matikan Kamera (Input Manual)"):
                st.session_state["tampilkan_scanner"] = False
                st.rerun()
                
            components.html(
                """
                <div id="qr-reader" style="width:100%; max-width:500px; margin:auto; border-radius:10px; border:2px solid #ddd; overflow:hidden;"></div>
                <div id="scan-result" style="text-align:center; height:30px; margin-top:10px; font-weight:bold; font-size:16px;">Mencari barcode...</div>
                <div style="text-align: center; margin-top: 5px;">
                    <button id="btn-switch" style="padding: 10px 20px; font-size: 14px; background-color: #007bff; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                        🔄 Ganti Kamera
                    </button>
                </div>
                <script src="https://unpkg.com/html5-qrcode"></script>
                <script>
                    function docReady(fn) {
                        if (document.readyState === "complete" || document.readyState === "interactive") { setTimeout(fn, 1); } 
                        else { document.addEventListener("DOMContentLoaded", fn); }
                    }
                    
                    function playBeep() {
                        try {
                            const AudioContext = window.AudioContext || window.webkitAudioContext;
                            const audioCtx = new AudioContext();
                            const oscillator = audioCtx.createOscillator();
                            const gainNode = audioCtx.createGain();
                            oscillator.type = 'sine';
                            oscillator.frequency.setValueAtTime(1000, audioCtx.currentTime); 
                            gainNode.gain.setValueAtTime(1, audioCtx.currentTime);
                            gainNode.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.15); 
                            oscillator.connect(gainNode);
                            gainNode.connect(audioCtx.destination);
                            oscillator.start();
                            oscillator.stop(audioCtx.currentTime + 0.15);
                        } catch(e) { console.log("Audio API not supported"); }
                        
                        if (navigator.vibrate) {
                            navigator.vibrate(200);
                        }
                    }

                    docReady(function () {
                        let currentFacingMode = "environment";
                        let isScanning = false;
                        let lastScanTime = 0;
                        let lastScannedText = "";
                        
                        const formatsToSupport = [
                            Html5QrcodeSupportedFormats.EAN_13,
                            Html5QrcodeSupportedFormats.CODE_128,
                            Html5QrcodeSupportedFormats.UPC_A
                        ];

                        const html5QrCode = new Html5Qrcode("qr-reader", { 
                            formatsToSupport: formatsToSupport,
                            experimentalFeatures: { useBarCodeDetectorIfSupported: true }
                        });

                        function onScanSuccess(decodedText, decodedResult) {
                            let currentTime = new Date().getTime();
                            if (decodedText === lastScannedText && (currentTime - lastScanTime) < 2000) {
                                return;
                            }
                            lastScanTime = currentTime;
                            lastScannedText = decodedText;
                            playBeep(); 
                            
                            document.getElementById('scan-result').innerHTML = `<span style="color:green;">✅ Berhasil: ${decodedText}</span>`;
                            
                            const parentDoc = window.parent.document;
                            const inputs = parentDoc.querySelectorAll('input');
                            inputs.forEach(input => {
                                if (input.getAttribute('aria-label') === 'Ketik Barcode atau Item Code (PLU):') {
                                    let nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                                    nativeSetter.call(input, decodedText);
                                    let ev = new Event('input', { bubbles: true});
                                    input.dispatchEvent(ev);
                                }
                            });
                        }

                        function startCamera() {
                            html5QrCode.start(
                                { facingMode: currentFacingMode },
                                { 
                                    fps: 15, 
                                    qrbox: { width: 280, height: 120 }, 
                                    disableFlip: true 
                                },
                                onScanSuccess,
                                (errorMessage) => { }
                            ).then(() => {
                                isScanning = true;
                            }).catch((err) => {
                                document.getElementById('scan-result').innerHTML = `<span style="color:red;">Kamera terblokir/gagal.</span>`;
                            });
                        }

                        document.getElementById('btn-switch').addEventListener('click', () => {
                            if (isScanning) {
                                html5QrCode.stop().then(() => {
                                    isScanning = false;
                                    currentFacingMode = (currentFacingMode === "environment") ? "user" : "environment";
                                    startCamera();
                                });
                            } else {
                                currentFacingMode = (currentFacingMode === "environment") ? "user" : "environment";
                                startCamera();
                            }
                        });

                        startCamera();
                    });
                </script>
                """,
                height=530,
            )

        st.markdown("---")
        st.write("📦 **Input Barang ke Database**")
        
        with st.form(key='form_scan', clear_on_submit=True):
            input_manual = st.text_input("Ketik Barcode atau Item Code (PLU):", placeholder="Contoh: 3337875829007 atau 3124761")
            qty_input = st.number_input("Jumlah (Qty):", min_value=1, value=1, step=1)
            submit_scan = st.form_submit_button("➕ Simpan Data", use_container_width=True)

        if submit_scan and input_manual:
            input_manual = input_manual.strip()
            df_live = load_data()
            
            kondisi_ibt = df_live['IBT No'] == pilih_ibt
            kondisi_barcode = df_live['Barcode'].astype(str) == input_manual
            kondisi_plu = df_live['PLU / Item Code'].astype(str) == input_manual
            
            pencarian = df_live[kondisi_ibt & (kondisi_barcode | kondisi_plu)]
            
            if not pencarian.empty:
                idx = pencarian.index[0]
                target = 1 # Target disesuaikan
                hasil_lama = int(df_live.at[idx, 'Hasil Cek Store'])
                hasil_baru = hasil_lama + qty_input
                
                status_baru = "✅ Sesuai" if hasil_baru == target else "⚠️ Over-receive"
                
                df_live.at[idx, 'Hasil Cek Store'] = hasil_baru
                df_live.at[idx, 'Status'] = status_baru
                save_data(df_live)
                
                st.success(f"Berhasil! {qty_input} pcs {df_live.at[idx, 'Nama Barang']} ditambahkan.")
            else:
                st.error(f"❌ Barang dengan kode '{input_manual}' TIDAK ADA dalam IBT {pilih_ibt}!")
    else:
        st.warning("⚠️ Database masih kosong. Minta Admin untuk meng-upload file PDF terlebih dahulu di komputer.")
