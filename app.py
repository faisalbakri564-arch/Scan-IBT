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

# --- FUNGSI BACA PDF ---
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
                    data_barang.append({
                        "IBT No": metadata["IBT No"],
                        "ERP No": metadata["ERP No"],
                        "Barcode": cocok.group(1),
                        "Nama Barang": cocok.group(2).strip(),
                        "Target IBT": int(cocok.group(4)),
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
        st.write("Data Saat Ini di Database:")
        st.dataframe(load_data(), use_container_width=True)

    with tab3:
        st.header("Koreksi & Download Laporan Akhir")
        df_curr = load_data()
        if not df_curr.empty:
            df_edit = st.data_editor(df_curr, num_rows="dynamic", use_container_width=True)
            save_data(df_edit)
            
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
        
        st.write("📷 **Live Barcode Scanner**")
        
        if "tampilkan_scanner" not in st.session_state:
            st.session_state["tampilkan_scanner"] = False
            
        if st.button("🔴 Buka Layar Scanner"):
            st.session_state["tampilkan_scanner"] = True
            
        if st.session_state["tampilkan_scanner"]:
            components.html(
                """
                <div id="qr-reader" style="width:100%; max-width:500px; margin:auto; border-radius:10px; border:2px solid #ddd; overflow:hidden;"></div>
                <div style="text-align: center; margin-top: 15px;">
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
                    
                    // FUNGSI SUARA & GETAR LANGSUNG DARI HARDWARE HP
                    function playBeep() {
                        try {
                            const AudioContext = window.AudioContext || window.webkitAudioContext;
                            const audioCtx = new AudioContext();
                            const oscillator = audioCtx.createOscillator();
                            const gainNode = audioCtx.createGain();
                            
                            oscillator.type = 'sine';
                            oscillator.frequency.setValueAtTime(1000, audioCtx.currentTime); // Frekuensi BEEP
                            
                            gainNode.gain.setValueAtTime(1, audioCtx.currentTime);
                            gainNode.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.15); // Bunyi sangat cepat
                            
                            oscillator.connect(gainNode);
                            gainNode.connect(audioCtx.destination);
                            
                            oscillator.start();
                            oscillator.stop(audioCtx.currentTime + 0.15);
                        } catch(e) { console.log("Audio API not supported"); }
                        
                        // Efek Getar HP 200ms
                        if (navigator.vibrate) {
                            navigator.vibrate(200);
                        }
                    }

                    docReady(function () {
                        let currentFacingMode = "environment";
                        let isScanning = false;
                        
                        // HANYA MENCARI BARCODE BARANG/KARDUS (Bikin scan jauh lebih responsif)
                        const formatsToSupport = [
                            Html5QrcodeSupportedFormats.EAN_13,
                            Html5QrcodeSupportedFormats.EAN_8,
                            Html5QrcodeSupportedFormats.CODE_128,
                            Html5QrcodeSupportedFormats.UPC_A
                        ];

                        const html5QrCode = new Html5Qrcode("qr-reader", { formatsToSupport: formatsToSupport });

                        function onScanSuccess(decodedText, decodedResult) {
                            playBeep(); // Panggil fungsi suara & getar
                            
                            if (isScanning) {
                                html5QrCode.stop().then(() => {
                                    isScanning = false;
                                    document.getElementById('qr-reader').innerHTML = `<h3 style="color:green; text-align:center; padding:20px;">✅ ${decodedText}</h3>`;
                                    document.getElementById('btn-switch').style.display = 'none';
                                });
                            }
                            
                            const parentDoc = window.parent.document;
                            const inputs = parentDoc.querySelectorAll('input');
                            inputs.forEach(input => {
                                if (input.getAttribute('aria-label') === 'Ketik 13 Digit Barcode:') {
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
                                    fps: 15, // Optimal untuk browser HP (tidak memberatkan CPU)
                                    qrbox: { width: 250, height: 100 }, // Kotak tipis memaksa fokus pas di garis barcode
                                    disableFlip: true // MATIKAN MIRRORING agar HP tidak nge-lag
                                },
                                onScanSuccess,
                                (errorMessage) => { }
                            ).then(() => {
                                isScanning = true;
                            }).catch((err) => {
                                document.getElementById('qr-reader').innerHTML = `<p style="color:red; text-align:center;">Gagal mengakses kamera.</p>`;
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
                height=500,
            )
            if st.button("Tutup Scanner"):
                st.session_state["tampilkan_scanner"] = False
                st.rerun()

        st.markdown("---")
        st.write("📦 **Input Barang ke Database**")
        with st.form(key='form_scan', clear_on_submit=True):
            barcode_manual = st.text_input("Ketik 13 Digit Barcode:", placeholder="Akan terisi otomatis jika pakai scanner...")
            qty_input = st.number_input("Jumlah (Qty):", min_value=1, value=1, step=1)
            submit_scan = st.form_submit_button("➕ Simpan Data", use_container_width=True)

        if submit_scan and barcode_manual:
            barcode_manual = barcode_manual.strip()
            df_live = load_data()
            
            kondisi_ibt = df_live['IBT No'] == pilih_ibt
            kondisi_barcode = df_live['Barcode'].astype(str) == barcode_manual
            pencarian = df_live[kondisi_ibt & kondisi_barcode]
            
            if not pencarian.empty:
                idx = pencarian.index[0]
                target = int(df_live.at[idx, 'Target IBT'])
                hasil_lama = int(df_live.at[idx, 'Hasil Cek Store'])
                hasil_baru = hasil_lama + qty_input
                
                status_baru = "✅ Sesuai" if hasil_baru == target else ("⚠️ Over-receive" if hasil_baru > target else "⏳ Kurang")
                
                df_live.at[idx, 'Hasil Cek Store'] = hasil_baru
                df_live.at[idx, 'Status'] = status_baru
                save_data(df_live)
                
                st.success(f"Berhasil! {qty_input} pcs {df_live.at[idx, 'Nama Barang']} ditambahkan.")
            else:
                st.error(f"❌ Barcode {barcode_manual} TIDAK ADA dalam IBT {pilih_ibt}!")
    else:
        st.warning("⚠️ Database masih kosong. Minta Admin untuk meng-upload file PDF terlebih dahulu di komputer.")
