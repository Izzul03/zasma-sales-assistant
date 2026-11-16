"""ZASMA Sales Assistant: price calculator, loan checklist, enquiry helper, lead dashboard.

DEMONSTRATION ENVIRONMENT: prices come from ZASMA HOME's public FAQ; all
customer enquiries are fictional.
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src import business_rules as br
from src.db import STAGES, LeadDB
from src.enquiry import INTENTS, assess, draft_reply, read_enquiry, read_enquiry_llm
from src.llm import LLM
from src.seed import seed_demo

st.set_page_config(page_title="ZASMA Sales Assistant", page_icon="🏡", layout="wide")

BLUE = "#2563ff"
st.markdown(f"""
<style>
.block-container {{padding-top: 3rem; max-width: 1250px;}}
[data-testid="stMetric"] {{background:#22262e; border:1px solid #2e333d; border-radius:14px; padding:14px 18px;}}
[data-testid="stMetricLabel"] p {{color:#9aa3b0;}}
.banner {{background: rgba(37,99,255,.12); border-left: 4px solid {BLUE}; padding: 10px 16px; border-radius: 8px;
  font-size: .9rem; color:#c9cfd8; margin-bottom: 1.2rem;}}
.big-price {{font-size: 2.6rem; font-weight: 800; color: #fff; line-height: 1.1;}}
.pill {{display:inline-block; padding:3px 10px; border-radius:999px; font-size:.8rem; margin-right:6px;}}
.ok {{background: rgba(34,197,94,.15); color:#22c55e;}} .no {{background: rgba(244,63,94,.15); color:#f43f5e;}}
.unk {{background: rgba(245,182,42,.15); color:#f5b62a;}}
</style>""", unsafe_allow_html=True)


@st.cache_resource
def get_db() -> LeadDB:
    db = LeadDB(Path(os.getenv("LEADS_DB", "data/leads.db")))
    if db.count() == 0:
        seed_demo(db)
    return db


db = get_db()
llm = LLM()


def rm(x) -> str:
    return "–" if x is None or pd.isna(x) else f"RM{x:,.0f}"


def plot(fig, h=320):
    fig.update_layout(template="plotly_dark", height=h, margin=dict(l=10, r=10, t=40, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      colorway=[BLUE, "#22c55e", "#f5b62a", "#a78bfa", "#f43f5e", "#94a3b8"])
    return fig


with st.sidebar:
    st.markdown("### 🏡 ZASMA Sales Assistant")
    st.caption("Pembantu jualan untuk kontraktor bina rumah atas tanah sendiri.")
    page = st.radio("Menu", ["🧮 Kalkulator Harga", "📋 Dokumen Pinjaman", "💬 Pembantu Pertanyaan",
                             "📊 Papan Pemuka Prospek", "ℹ️ Tentang Projek Ini"], label_visibility="collapsed")
    st.divider()
    salesperson = st.selectbox("Jurujual (demo)", ["Demo Jurujual A", "Demo Jurujual B", "Demo Sales Manager"])
    st.caption("Mod AI: " + (f"{llm.provider} · {llm.model}" if llm.enabled else "luar talian (tanpa kunci API)"))

st.markdown("<div class='banner'>🧪 <b>DEMO</b>: harga diambil daripada Soalan Lazim awam ZASMA HOME. Semua "
            "pertanyaan pelanggan adalah <b>rekaan</b>. Ini projek peribadi, bukan sistem rasmi ZASMA.</div>",
            unsafe_allow_html=True)


# ------------------------------------------------------------------ 1. calculator
def page_calculator():
    st.title("Kalkulator Harga Rumah")
    st.write("Dapatkan anggaran harga dan tempoh bina dalam beberapa saat.")
    left, right = st.columns([1, 1.2], gap="large")
    with left:
        sqft = st.slider("Keluasan rumah (kaki persegi)", 800, 4000, 1500, step=50)
        storeys = st.radio("Bilangan tingkat", [1, 2], format_func=lambda x: f"{x} tingkat", horizontal=True)
        spec = st.radio("Spesifikasi", list(br.RATES_PER_SQFT), format_func=lambda s: br.SPEC_LABELS[s],
                        horizontal=True)
        st.markdown("##### Anggaran bayaran bulanan (pilihan)")
        down = st.number_input("Wang pendahuluan / KWSP Akaun 2 (RM)", 0, 500_000, 0, step=1000)
        rate = st.number_input("Kadar faedah / keuntungan setahun (%)", 0.0, 10.0, 4.0, step=0.1,
                               help="Ini andaian anda sendiri. Kadar sebenar bergantung pada bank atau LPPSA.")
        years = st.slider("Tempoh pinjaman (tahun)", 5, 35, 30)
    est = br.estimate_price(sqft, spec, storeys)
    loan = max(est.price - down, 0)
    monthly = br.monthly_instalment(loan, rate, years)
    with right:
        st.markdown("##### Anggaran harga rumah")
        st.markdown(f"<div class='big-price'>{rm(est.price)}</div>", unsafe_allow_html=True)
        st.caption(f"{sqft:,} kps × RM{est.rate:.0f} sekaki persegi ({spec})")
        c1, c2 = st.columns(2)
        c1.metric("Tempoh pembinaan", est.months_text)
        c2.metric("Anggaran ansuran bulanan", rm(monthly), help=f"Pinjaman {rm(loan)}, {rate}% setahun, {years} tahun")
        compare = pd.DataFrame([
            {"Spesifikasi": br.SPEC_LABELS[s], "Harga": br.estimate_price(sqft, s, storeys).price}
            for s in br.RATES_PER_SQFT])
        fig = px.bar(compare, x="Spesifikasi", y="Harga", text="Harga", title="Perbandingan spesifikasi")
        fig.update_traces(texttemplate="RM%{text:,.0f}", textposition="outside", marker_color=BLUE)
        fig.update_yaxes(range=[0, compare["Harga"].max() * 1.2])
        st.plotly_chart(plot(fig, 280), use_container_width=True, theme=None)
        st.info("ℹ️ Ini **anggaran awal** berdasarkan harga yang dipaparkan di laman web ZASMA. Harga sebenar "
                "bergantung pada reka bentuk dan keadaan tapak, dan mesti disahkan oleh jurujual. "
                f"Sumber: {br.SOURCE_URL}")
        st.caption("Contoh dalam Soalan Lazim ZASMA: rumah 1,500 kps (4 bilik, 3 bilik air) sekitar RM232k.")


# ------------------------------------------------------------------ 2. documents
def page_documents():
    st.title("Senarai Semak Dokumen Pinjaman")
    st.write("Pilih jenis pekerjaan pelanggan. Sistem akan memaparkan dokumen yang perlu disediakan.")
    seg = st.radio("Pelanggan bekerja sebagai:", list(br.LOAN_DOCUMENTS),
                   format_func=lambda s: br.LOAN_DOCUMENTS[s]["label"], horizontal=True)
    info = br.LOAN_DOCUMENTS[seg]
    st.success(f"**Pembiayaan biasa:** {info['financing']}")
    st.markdown("##### Dokumen yang disenaraikan oleh ZASMA")
    done = [st.checkbox(d, key=f"doc_{seg}_{d}") for d in info["documents"]]
    st.markdown("##### Biasanya juga diperlukan (perlu disahkan dengan ZASMA)")
    done += [st.checkbox(d, key=f"doc_c_{seg}_{d}") for d in br.COMMON_DOCUMENTS_TO_CONFIRM]
    total = len(info["documents"]) + len(br.COMMON_DOCUMENTS_TO_CONFIRM)
    st.progress(sum(done) / total, text=f"{sum(done)} daripada {total} dokumen sedia")
    text = "\n".join([f"Senarai dokumen: {info['label']}", f"Pembiayaan: {info['financing']}", ""]
                     + [f"[ ] {d}" for d in info["documents"]]
                     + ["", "Perlu disahkan:"] + [f"[ ] {d}" for d in br.COMMON_DOCUMENTS_TO_CONFIRM])
    st.download_button("⬇️ Muat turun senarai (untuk dihantar kepada pelanggan)", text,
                       file_name=f"senarai_dokumen_{seg}.txt")
    st.caption(f"Sumber: {br.SOURCE_URL}")


# ------------------------------------------------------------------ 3. enquiry helper
EXAMPLES = [
    "Assalamualaikum, nama saya Aminah. Saya cikgu, ada tanah sendiri di Pasir Mas. Nak bina rumah setingkat "
    "1500 kps, 4 bilik. Bajet RM220k. Boleh mohon LPPSA?",
    "salam, saya kerja kilang di KL tapi tanah ayah di Machang. berapa harga rumah 2 tingkat 2400 sqft premium?",
    "Hi, boleh bina rumah di Kuala Terengganu? bajet 300 ribu",
    "nak tanya, takde tanah lagi. boleh tolong carikan tanah dan bina sekali?",
]


def page_enquiry():
    st.title("Pembantu Pertanyaan Pelanggan")
    st.write("Tampal mesej pelanggan (contohnya dari WhatsApp). Sistem akan membaca maklumat penting dan "
             "menyediakan **draf jawapan**. Anda semak dan ubah dahulu sebelum menghantar. Sistem tidak "
             "menghantar apa-apa secara automatik.")
    ex = st.selectbox("Atau pilih contoh mesej", ["(tulis sendiri)"] + EXAMPLES)
    msg = st.text_area("Mesej pelanggan", value="" if ex == "(tulis sendiri)" else ex, height=110)
    use_llm = st.toggle("Gunakan AI (LLM) untuk membaca mesej", value=False, disabled=not llm.enabled,
                        help="Perlukan kunci API. Tanpa kunci, sistem guna pembaca kata kunci.")
    if not msg.strip():
        return
    try:
        info = read_enquiry_llm(msg, llm) if use_llm else read_enquiry(msg)
    except Exception as exc:
        st.warning(f"AI gagal ({exc}). Menggunakan pembaca kata kunci.")
        info = read_enquiry(msg)
    a = assess(info)

    c1, c2 = st.columns([1, 1.3], gap="large")
    with c1:
        st.markdown("##### Maklumat yang dikesan")
        cov = a["coverage"]
        cls = {"covered": "ok", "not_covered": "no"}.get(cov["status"], "unk")
        label = {"covered": "Dalam kawasan liputan", "not_covered": "Luar kawasan"}.get(cov["status"], "Perlu disahkan")
        st.markdown(f"<span class='pill {cls}'>{label}</span>", unsafe_allow_html=True)
        rows = {
            "Nama": info.name, "Lokasi tanah": info.place,
            "Pekerjaan": br.LOAN_DOCUMENTS[info.segment]["label"] if info.segment else None,
            "Bajet": rm(info.budget) if info.budget else None,
            "Saiz": f"{info.sqft:,.0f} kps" if info.sqft else None,
            "Bilik": info.bedrooms, "Tingkat": info.storeys,
            "Ada tanah sendiri": {True: "Ya", False: "Tidak"}.get(info.has_land),
            "Tujuan mesej": ", ".join(INTENTS[i] for i in info.intents),
        }
        st.dataframe(pd.DataFrame([(k, "–" if v in (None, "") else str(v)) for k, v in rows.items()],
                                  columns=["Perkara", "Nilai"]), hide_index=True, use_container_width=True)
        if a["estimate"]:
            st.metric("Anggaran harga (dikira oleh sistem)", rm(a["estimate"].price))
            st.caption(f"Tempoh bina: {a['estimate'].months_text}")
        if a["missing"]:
            st.warning("Maklumat belum ada: " + ", ".join(a["missing"]))
        st.caption(f"Dibaca menggunakan: {'AI' if info.method == 'llm' else 'pembaca kata kunci'}")
    with c2:
        st.markdown("##### Draf jawapan (semak dan ubah sebelum hantar)")
        reply = st.text_area("Draf", value=draft_reply(info, a), height=380, label_visibility="collapsed")
        b1, b2 = st.columns(2)
        if b1.button("💾 Simpan sebagai prospek baharu", use_container_width=True, theme=None):
            lead_id = db.add_lead(msg, info.to_dict(), cov["status"], a["estimate"].price if a["estimate"] else None,
                                  reply)
            st.session_state["last_lead"] = lead_id
            st.success(f"Disimpan sebagai prospek #{lead_id}.")
        if b2.button("✅ Saya sudah hantar jawapan ini", type="primary", use_container_width=True, theme=None):
            lead_id = st.session_state.get("last_lead") or db.add_lead(
                msg, info.to_dict(), cov["status"], a["estimate"].price if a["estimate"] else None, reply)
            db.mark_replied(lead_id, reply, salesperson)
            st.session_state.pop("last_lead", None)
            st.success(f"Direkodkan: prospek #{lead_id} sudah dihubungi oleh {salesperson}. Susulan dalam 3 hari.")


# ------------------------------------------------------------------ 4. dashboard
def page_dashboard():
    st.title("Papan Pemuka Prospek")
    df = pd.DataFrame(db.leads())
    if df.empty:
        st.info("Belum ada prospek.")
        return
    df["created"] = pd.to_datetime(df["created_at"])
    today = date.today().isoformat()
    active = df[~df["stage"].isin(["Tandatangan", "Tidak berminat"])]
    overdue = active[active["follow_up_due"] < today]
    c = st.columns(4)
    c[0].metric("Jumlah pertanyaan", len(df))
    c[1].metric("Prospek aktif", len(active))
    c[2].metric("Perlu disusuli (lewat)", len(overdue))
    signed = (df["stage"] == "Tandatangan").sum()
    c[3].metric("Kadar tandatangan", f"{signed / len(df) * 100:.0f}%")

    l, r = st.columns(2)
    with l:
        funnel = df["stage"].value_counts().reindex(STAGES, fill_value=0).reset_index()
        funnel.columns = ["Peringkat", "Bilangan"]
        st.plotly_chart(plot(px.funnel(funnel, x="Bilangan", y="Peringkat", title="Perjalanan prospek")),
                        use_container_width=True, theme=None)
    with r:
        place = df["place"].fillna("Tidak dinyatakan").value_counts().reset_index()
        place.columns = ["Lokasi", "Bilangan"]
        st.plotly_chart(plot(px.bar(place.sort_values("Bilangan"), x="Bilangan", y="Lokasi", orientation="h",
                                    title="Pertanyaan mengikut lokasi tanah").update_traces(marker_color=BLUE)),
                        use_container_width=True, theme=None)
    l, r = st.columns(2)
    with l:
        weekly = df.set_index("created").resample("W")["id"].count().reset_index()
        weekly.columns = ["Minggu", "Pertanyaan"]
        st.plotly_chart(plot(px.line(weekly, x="Minggu", y="Pertanyaan", markers=True,
                                     title="Pertanyaan setiap minggu")), use_container_width=True, theme=None)
    with r:
        seg = df["segment"].map(lambda s: br.LOAN_DOCUMENTS[s]["label"] if s in br.LOAN_DOCUMENTS else "Belum diketahui")
        sc = seg.value_counts().reset_index()
        sc.columns = ["Pekerjaan", "Bilangan"]
        st.plotly_chart(plot(px.pie(sc, names="Pekerjaan", values="Bilangan", hole=.55,
                                    title="Jenis pekerjaan pelanggan")), use_container_width=True, theme=None)

    st.subheader("🔔 Prospek yang perlu disusuli")
    show = overdue.sort_values("follow_up_due")[["id", "name", "place", "budget", "stage", "follow_up_due", "message"]]
    show = show.rename(columns={"id": "#", "name": "Nama", "place": "Lokasi", "budget": "Bajet (RM)",
                                "stage": "Peringkat", "follow_up_due": "Tarikh susulan", "message": "Mesej"})
    st.dataframe(show.fillna("–"), hide_index=True, use_container_width=True)

    st.subheader("Kemas kini prospek")
    pick = st.selectbox("Pilih prospek", df["id"].tolist(),
                        format_func=lambda i: f"#{i} · {df.loc[df['id'] == i, 'name'].iloc[0] or 'Tanpa nama'} · "
                                              f"{df.loc[df['id'] == i, 'place'].iloc[0] or '-'}")
    lead = db.lead(int(pick))
    cA, cB = st.columns([1.3, 1])
    with cA:
        st.caption("Mesej asal")
        st.write(lead["message"])
        with st.expander("Draf / jawapan yang dihantar"):
            st.text(lead["final_reply"] or lead["draft_reply"])
    with cB:
        new_stage = st.selectbox("Peringkat", STAGES, index=STAGES.index(lead["stage"]))
        due = st.date_input("Tarikh susulan seterusnya", value=pd.to_datetime(lead["follow_up_due"]).date())
        if st.button("Simpan perubahan", type="primary"):
            db.set_stage(lead["id"], new_stage, salesperson, due.isoformat())
            st.success("Dikemas kini.")
            st.rerun()
        with st.expander("Sejarah"):
            st.dataframe(pd.DataFrame(db.log(lead["id"]))[["at", "actor", "action", "details"]],
                         hide_index=True, use_container_width=True)


def page_about():
    st.title("Tentang Projek Ini")
    st.markdown(f"""
**ZASMA Sales Assistant** ialah projek peribadi oleh **Muhammad Izzul Fidaey** untuk menunjukkan bagaimana
alat digital ringkas boleh membantu pasukan jualan sebuah kontraktor bina rumah.

**Apa yang ia buat**
1. **Kalkulator harga**: anggaran segera berdasarkan harga per kaki persegi yang dipaparkan secara awam.
2. **Senarai dokumen pinjaman**: mengikut jenis pekerjaan pelanggan.
3. **Pembantu pertanyaan**: membaca mesej pelanggan dan menyediakan draf jawapan. **Jurujual sentiasa
   menyemak sebelum menghantar.**
4. **Papan pemuka prospek**: supaya tiada pelanggan yang terlepas susulan.

**Prinsip keselamatan**
- Harga sentiasa **dikira oleh sistem** daripada jadual harga, bukan direka oleh AI.
- Tiada mesej dihantar secara automatik.
- Data pelanggan dalam demo ini **rekaan**. Dalam penggunaan sebenar, data peribadi perlu dilindungi
  mengikut PDPA.

**Had**
- Harga dan tempoh diambil daripada Soalan Lazim awam ({br.SOURCE_URL}) pada 16 Nov 2026, dan mungkin
  sudah berubah.
- Pembaca kata kunci memahami ayat biasa, tetapi mungkin terlepas loghat atau ejaan pelik. Mod AI
  membantu, tetapi memerlukan kunci API.
- Tiada integrasi WhatsApp sebenar dalam demo ini.
""")
    if st.button("♻️ Set semula data demo"):
        db.reset()
        seed_demo(db)
        st.success("Data demo dimuat semula.")


{"🧮 Kalkulator Harga": page_calculator, "📋 Dokumen Pinjaman": page_documents,
 "💬 Pembantu Pertanyaan": page_enquiry, "📊 Papan Pemuka Prospek": page_dashboard,
 "ℹ️ Tentang Projek Ini": page_about}[page]()
