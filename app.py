import streamlit as st
import pandas as pd
import pdfplumber
import re
import os
import io
import barcode
from barcode.writer import ImageWriter
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import streamlit.components.v1 as components

# --- MENGATUR TAMPILAN HALAMAN WEB ---
st.set_page_config(page_title="Receiving IBT Guardian", layout="wide", page_icon="📦")

# CSS Kustom untuk mempercantik tampilan (warna lembut/pastel transparan)
st.markdown("""
    <style>
    .staff-section {
        background-color: rgba(54, 162, 235, 0.1);
        padding: 20px;
        border-radius: 12px;
        border: 1px solid rgba(54, 162, 235, 0.3);
        margin-bottom: 20px;
    }
    .staff-form {
        background-color: rgba(75, 192, 192, 0.1);
        padding: 20px;
        border-radius: 12px;
        border: 1px solid rgba(75, 192, 192, 0.3);
        margin-bottom: 20px;
    }
    .header-text {
        color: #2e86c1;
    }
    </style>
""", unsafe_allow_html=True)

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

# --- FUNGSI BACA PDF ---
def baca_pdf_ibt_multi(file_pdf):
    data_barang = []
    metadata = {"IBT No": "-", "Store Info": "-"}
    with pdfplumber.open(file_pdf) as pdf:
        for halaman in pdf.pages:
            teks = halaman.extract_text()
            
            match_ibt = re.search(r'IBT No\.:\s*(\S+)', teks)
            if match_ibt: metadata["IBT No"] = match_ibt.group(1)
            
            # Mencari baris IBT-in Store
            match_store = re.search(r'IBT-in Store:\s*(.+)', teks)
            if match_store: 
                 store_info_raw = match_store.group(1)
                 store_info_clean = store_info_raw.split("IBT-out Store:")[0].strip()
                 metadata["Store Info"] = store_info_clean
            
            baris_teks = teks.split("\n")
            for baris in baris_teks:
                # Regex aman untuk nama barang panjang
                cocok = re.search(r'\d+\s+.*?\s+(\d{6,7})\s+(\d{12,13})\s+(.+?)\s+EA\s+(\d+)', baris)
                
                if cocok:
                    item_code = cocok.group(1)
                    barcode = cocok.group(2)
                    nama_lengkap = " ".join(cocok.group(3).strip().split()) # Merapikan spasi
                    target_qty = int(cocok.group(4))
                    
                    data_barang.append({
                        "IBT No": metadata["IBT No"],
                        "Store Info": metadata["Store Info"],
                        "Barcode": barcode,
                        "PLU / Item Code": item_code,
                        "Nama Barang": nama_lengkap,
                        "Target IBT": target_qty,
                        "Hasil Cek Store": 0,
                        "Kondisi Barang / Reason": "",
                        "Status": "Belum Dicek"
                    })
    return pd.DataFrame(data_barang)

# --- FUNGSI GENERATE PDF BERITA ACARA ---
def generate_pdf_report(df_filtered, ibt_no, store_info):
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, alignment=1, spaceAfter=10)
    normal_style = ParagraphStyle('NormalStyle', parent=styles['Normal'], fontSize=10)
    
    elements.append(Paragraph(f"<b>BERITA ACARA RECEIVING IBT</b>", title_style))
    elements.append(Paragraph(f"<b>Nomor IBT:</b> {ibt_no}", normal_style))
    elements.append(Paragraph(f"<b>IBT-in Store:</b> {store_info}", normal_style))
    elements.append(Spacer(1, 15))
    
    # Barcode IBT
    try:
        code128 = barcode.get('code128', ibt_no, writer=ImageWriter())
        barcode_filename = f"barcode_{ibt_no}"
        code128.save(barcode_filename)
        elements.append(RLImage(barcode_filename + ".png", width=180, height=45))
        elements.append(Spacer(1, 15))
    except Exception:
        pass

    # Tabel Data (Dengan Word Wrap otomatis pada Nama Barang)
    table_data = [["No", "PLU / Item Code", "Nama Barang", "Target", "Hasil Cek", "Kondisi / Reason", "Status"]]
    for idx, row in df_filtered.reset_index(drop=True).iterrows():
        nama_barang_p = Paragraph(str(row['Nama Barang']), styles['Normal'])
        kondisi_p = Paragraph(str(row['Kondisi Barang / Reason']), styles['Normal'])
        
        table_data.append([
            str(idx + 1),
            str(row['PLU / Item Code']),
            nama_barang_p, 
            str(row['Target IBT']),
            str(row['Hasil Cek Store']),
            kondisi_p, 
            str(row['Status'])
        ])
        
    t = Table(table_data, colWidths=[25, 75, 185, 45, 55, 95, 60])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#003366')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 40))
    
    # Kolom Tanda Tangan
    sig_data = [
        ["Mengetahui,", "Mengetahui,"],
        ["", ""],
        ["_________________________", "_________________________"],
        ["Store Leader (SL)", "Area Manager (AM)"]
    ]
    sig_table = Table(sig_data, colWidths=[200, 200])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,1), (-1,1), 40), 
    ]))
    elements.append(sig_table)
    
    doc.build(elements)
    pdf_buffer.seek(0)
    return pdf_buffer.getvalue()

# ==========================================
# PENGATURAN STATE & NAVIGASI SIDEBAR
# ==========================================
if 'role' not in st.session_state:
    st.session_state['role'] = None

with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/c/cb/Guardian_Pharmacy_logo.svg/1024px-Guardian_Pharmacy_logo.svg.png", width=150)
    st.title("Sistem Receiving IBT Guardian Makasar Hero Nipah Mall")
    st.markdown("---")
    
    # JIKA BELUM PILIH PERAN
    if st.session_state['role'] is None:
        st.subheader("Pilih Peran Anda:")
        if st.button("💻 Masuk sbg Admin", use_container_width=True, type="primary"):
            st.session_state['role'] = "Admin"
            st.rerun()
        if st.button("📱 Masuk sbg Staff", use_container_width=True):
            st.session_state['role'] = "Staff"
            st.rerun()
            
    # JIKA ADMIN
    elif st.session_state['role'] == "Admin":
        st.subheader("👤 Menu Admin")
        menu_admin = st.radio("Navigasi:", ["📥 Upload Data PDF", "📝 Download Data"])
        st.markdown("---")
        if st.button("⬅️ Ganti Peran", use_container_width=True):
            st.session_state['role'] = None
            st.rerun()
            
    # JIKA STAFF
    elif st.session_state['role'] == "Staff":
        st.subheader("👤 Menu Staff")
        st.info("Mode Pengecekan Aktif")
        st.markdown("---")
        if st.button("⬅️ Ganti Peran", use_container_width=True):
            st.session_state['role'] = None
            st.rerun()

    # TOMBOL RESET GLOBAL DI BAWAH SIDEBAR
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("---")
    st.warning("⚙️ Zona Bahaya")
    if st.button("🗑️ Hapus Seluruh Data", type="primary", use_container_width=True):
        hapus_semua_data()
        st.session_state['role'] = None
        st.success("Data direset!")
        import time
        time.sleep(1)
        st.rerun()

# ==========================================
# HALAMAN UTAMA (MAIN AREA)
# ==========================================
if st.session_state['role'] is None:
    st.markdown("<h2 style='text-align: center; color: gray; margin-top:100px;'>Silakan pilih peran di menu sebelah kiri 👈</h2>", unsafe_allow_html=True)

# ----------------- ADMIN -----------------
elif st.session_state['role'] == "Admin":
    st.title(f"{menu_admin}")
    
    if menu_admin == "📥 Upload Data PDF":
        st.write("Silakan upload dokumen IBT PDF baru ke dalam sistem.")
        file_uploads = st.file_uploader("Upload file PDF IBT (Maks 10 file):", type=["pdf"], accept_multiple_files=True)
        
        if st.button("Proses Upload ke Database", type="primary"):
            if file_uploads:
                semua_df = []
                for file in file_uploads:
                    semua_df.append(baca_pdf_ibt_multi(file))
                if semua_df:
                    df_gabung = pd.concat(semua_df, ignore_index=True)
                    save_data(df_gabung)
                    st.success("✅ Data berhasil disimpan! Staf di HP sudah bisa mulai mengecek.")
            else:
                st.warning("Pilih file PDF terlebih dahulu!")
                
    elif menu_admin == "📝 Download Data":
        df_curr = load_data()
        
        if not df_curr.empty and 'IBT No' in df_curr.columns:
            daftar_ibt = list(df_curr['IBT No'].unique())
            pilih_ibt_admin = st.selectbox("📌 Pilih dokumen IBT yang akan dikelola:", daftar_ibt)
            
            df_filter = df_curr[df_curr['IBT No'] == pilih_ibt_admin]
            
            col1, col2 = st.columns([8, 2])
            with col1:
                st.write("Silakan koreksi jumlah Qty atau Kondisi Barang jika ada selisih sebelum mencetak:")
            with col2:
                if st.button("🔄 Segarkan Data", use_container_width=True):
                    st.rerun()

            # Menampilkan tabel data
            df_edit = st.data_editor(df_filter, use_container_width=True)
            
            # Update Status Otomatis
            for i in df_edit.index:
                target = int(df_edit.at[i, 'Target IBT'])
                hasil = int(df_edit.at[i, 'Hasil Cek Store'])
                if hasil == target:
                    df_edit.at[i, 'Status'] = "Sesuai"
                elif hasil > target:
                    df_edit.at[i, 'Status'] = "Over-receive"
                elif hasil > 0:
                    df_edit.at[i, 'Status'] = "Kurang"
                else:
                    df_edit.at[i, 'Status'] = "Belum Dicek"

            df_curr.update(df_edit)
            save_data(df_curr)
            
            st.markdown("---")
            store_info = df_edit['Store Info'].iloc[0] if 'Store Info' in df_edit.columns and not df_edit.empty else "-"
            
            pdf_bytes = generate_pdf_report(df_edit, pilih_ibt_admin, store_info)
            st.download_button(
                label=f"📄 Download Laporan PDF ({pilih_ibt_admin})",
                data=pdf_bytes,
                file_name=f"Berita_Acara_Receiving_{pilih_ibt_admin}.pdf",
                mime='application/pdf',
                type="primary"
            )
        else:
            st.info("Belum ada data di database. Silakan upload PDF terlebih dahulu.")

# ----------------- STAFF -----------------
elif st.session_state['role'] == "Staff":
    st.title("📱 Pengecekan Barang IBT")
    
    df_data = load_data()
    
    if not df_data.empty and 'IBT No' in df_data.columns:
        daftar_ibt = df_data['IBT No'].unique()
        pilih_ibt = st.selectbox("📌 Dokumen IBT Aktif:", daftar_ibt)
        st.markdown("---")
        
        # Area Scanner dengan background lembut
        st.markdown('<div class="staff-section">', unsafe_allow_html=True)
        st.markdown("<h4>📷 Scanner Kamera (Opsional)</h4>", unsafe_allow_html=True)
        
        if "tampilkan_scanner" not in st.session_state:
            st.session_state["tampilkan_scanner"] = False
            
        if not st.session_state["tampilkan_scanner"]:
            if st.button("📸 Hidupkan Scanner Kamera"):
                st.session_state["tampilkan_scanner"] = True
                st.rerun()
        else:
            if st.button("❌ Matikan Kamera"):
                st.session_state["tampilkan_scanner"] = False
                st.rerun()
                
            components.html(
                """
                <div id="qr-reader" style="width:100%; max-width:500px; margin:auto; border-radius:10px; border:2px solid #ccc; overflow:hidden;"></div>
                <div id="scan-result" style="text-align:center; height:30px; margin-top:10px; font-weight:bold; font-size:16px;">Mencari barcode...</div>
                <div style="text-align: center; margin-top: 5px;">
                    <button id="btn-switch" style="padding: 8px 16px; font-size: 14px; background-color: #007bff; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
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
                        } catch(e) {}
                        if (navigator.vibrate) { navigator.vibrate(200); }
                    }
                    docReady(function () {
                        let currentFacingMode = "environment";
                        let isScanning = false;
                        let lastScanTime = 0;
                        let lastScannedText = "";
                        const html5QrCode = new Html5Qrcode("qr-reader", { experimentalFeatures: { useBarCodeDetectorIfSupported: true } });
                        function onScanSuccess(decodedText) {
                            let currentTime = new Date().getTime();
                            if (decodedText === lastScannedText && (currentTime - lastScanTime) < 2000) return;
                            lastScanTime = currentTime;
                            lastScannedText = decodedText;
                            playBeep(); 
                            document.getElementById('scan-result').innerHTML = `<span style="color:green;">✅ Scan: ${decodedText}</span>`;
                            const inputs = window.parent.document.querySelectorAll('input');
                            inputs.forEach(input => {
                                if (input.getAttribute('aria-label') === 'Ketik Barcode atau Item Code (PLU):') {
                                    let nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                                    nativeSetter.call(input, decodedText);
                                    input.dispatchEvent(new Event('input', { bubbles: true}));
                                }
                            });
                        }
                        function startCamera() {
                            html5QrCode.start({ facingMode: currentFacingMode }, { fps: 15, qrbox: { width: 280, height: 120 }, disableFlip: true }, onScanSuccess).then(() => { isScanning = true; });
                        }
                        document.getElementById('btn-switch').addEventListener('click', () => {
                            if (isScanning) { html5QrCode.stop().then(() => { isScanning = false; currentFacingMode = (currentFacingMode === "environment") ? "user" : "environment"; startCamera(); }); } 
                            else { currentFacingMode = (currentFacingMode === "environment") ? "user" : "environment"; startCamera(); }
                        });
                        startCamera();
                    });
                </script>
                """, height=500
            )
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Area Input dengan background lembut
        st.markdown('<div class="staff-form">', unsafe_allow_html=True)
        st.markdown("<h4>📦 Input Manual / Hasil Scan</h4>", unsafe_allow_html=True)
        
        with st.form(key='form_scan', clear_on_submit=True):
            input_manual = st.text_input("Ketik Barcode atau Item Code (PLU):")
            qty_input = st.number_input("Jumlah (Qty):", min_value=1, value=1, step=1)
            reason_input = st.text_input("Kondisi Barang / Reason (Opsional, isi jika ada masalah/selisih):")
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
                target = int(df_live.at[idx, 'Target IBT'])
                hasil_lama = int(df_live.at[idx, 'Hasil Cek Store'])
                hasil_baru = hasil_lama + qty_input
                status_baru = "Sesuai" if hasil_baru == target else ("Over-receive" if hasil_baru > target else "Kurang")
                
                df_live.at[idx, 'Hasil Cek Store'] = hasil_baru
                df_live.at[idx, 'Status'] = status_baru
                
                if reason_input.strip():
                    alasan_lama = str(df_live.at[idx, 'Kondisi Barang / Reason'])
                    if alasan_lama and alasan_lama != "nan":
                        df_live.at[idx, 'Kondisi Barang / Reason'] = alasan_lama + "; " + reason_input.strip()
                    else:
                        df_live.at[idx, 'Kondisi Barang / Reason'] = reason_input.strip()
                        
                save_data(df_live)
                st.success(f"✅ Berhasil! {qty_input} pcs '{df_live.at[idx, 'Nama Barang']}' ditambahkan.")
            else:
                st.error(f"❌ Barang dengan kode '{input_manual}' TIDAK ADA dalam IBT {pilih_ibt}!")
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.warning("⚠️ Database masih kosong. Minta Admin untuk meng-upload file PDF terlebih dahulu.")
