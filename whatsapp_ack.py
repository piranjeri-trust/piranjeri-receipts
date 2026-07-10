"""
whatsapp_ack.py
Piranjeri Temples Family Trust — WhatsApp Acknowledgement Section
Renders as a separate section below the existing app content.
Does NOT modify any existing app logic.
"""
import streamlit as st
import psycopg2
import psycopg2.extras
import urllib.parse
from datetime import datetime
# ── Purposes (mirrored from app.py — do not change) ───────────────────────
PURPOSES = [
    "Nithya Pooja", "Garuda Seva", "Pradhosham", "Sangabhishekam",
    "Panguni uthiram", "Annadhanam", "Kumbhabhishekam", "Varushabhishekam",
    "Temple Renovation", "General Donation"
]
# ── DB helpers ─────────────────────────────────────────────────────────────
def _get_conn():
    if "neon_conn" not in st.session_state or st.session_state["neon_conn"] is None:
        dsn = st.secrets["neon"]["dsn"]
        conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
        conn.autocommit = False
        st.session_state["neon_conn"] = conn
    else:
        conn = st.session_state["neon_conn"]
        try:
            conn.cursor().execute("SELECT 1")
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            dsn = st.secrets["neon"]["dsn"]
            conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
            conn.autocommit = False
            st.session_state["neon_conn"] = conn
    return conn
def _save_ack_log(record: dict):
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO whatsapp_ack_log
                    (donor_name, mobile, amount, purpose, note,
                     prasadham, message, sent_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                record["donor_name"],
                record["mobile"],
                float(record["amount"]),
                record["purpose"],
                record.get("note", ""),
                record["prasadham"],
                record["message"],
                record["sent_by"],
            ))
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
def _load_ack_log(search_mobile: str = "") -> list:
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            if search_mobile.strip():
                digits = "".join(c for c in search_mobile if c.isdigit())
                cur.execute("""
                    SELECT * FROM whatsapp_ack_log
                    WHERE mobile LIKE %s
                    ORDER BY sent_at DESC
                """, (f"%{digits}%",))
            else:
                cur.execute("""
                    SELECT * FROM whatsapp_ack_log
                    ORDER BY sent_at DESC
                    LIMIT 100
                """)
            rows = cur.fetchall()
        conn.commit()
        return [dict(r) for r in rows]
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return []
# ── All widget keys used in this section ──────────────────────────────────
_ACK_WIDGET_KEYS = [
    "ack_search_mobile",
    "ack_donor_select",
    "ack_amount",
    "ack_purpose",
    "ack_note",
    "ack_prasadham",
    "ack_wa_url",
    "ack_wa_name",
    "ack_message_preview",
]

# ── Main render function ───────────────────────────────────────────────────
def render_whatsapp_ack_section(donors, current_user: str):
    st.divider()
    st.subheader("📲 WhatsApp Acknowledgement")
    st.caption(
        "Search by WhatsApp number to find the donor, select them, "
        "enter the amount and purpose, then generate the acknowledgement link."
    )
    if donors.empty:
        st.warning("No donors found. Add a donor in the section above first.")
        return
    # ── STEP 1: Search by WhatsApp number ────────────────────────
    search_mobile = st.text_input(
        "🔍 Search donor by WhatsApp number",
        key="ack_search_mobile",
        placeholder="Enter digits to filter donor list"
    )
    # Filter donor list based on search
    if search_mobile.strip():
        digits = "".join(c for c in search_mobile if c.isdigit())
        filtered = donors[
            donors["Mobile Number"].astype(str).str.contains(digits, na=False)
        ]
    else:
        filtered = donors
    # ── STEP 2: Select donor from (filtered) dropdown ─────────────
    if filtered.empty:
        st.warning("No donor found with that WhatsApp number.")
        return
    donor_options = [
        r["NAME"] if not r["Mobile Number"] or r["Mobile Number"] in ("", "nan")
        else f"{r['NAME']} - {r['Mobile Number']}"
        for _, r in filtered.iterrows()
    ]
    ack_selected = st.selectbox(
        "Select donor",
        options=["-- Select donor --"] + donor_options,
        key="ack_donor_select"
    )
    if ack_selected == "-- Select donor --":
        # Still show the log below even if no donor selected
        _render_log()
        return
    ack_index = filtered.index[donor_options.index(ack_selected)]
    ack_donor_name = filtered.loc[ack_index, "NAME"]
    ack_donor_mobile = str(filtered.loc[ack_index, "Mobile Number"])
    # ── STEP 3: Amount, Purpose, Note, Prasadham ─────────────────
    col1, col2 = st.columns(2)
    with col1:
        ack_amount = st.number_input(
            "Amount informed by donor (Rs.)",
            min_value=1.0, step=1.0, format="%.2f",
            key="ack_amount"
        )
        ack_purpose = st.selectbox(
            "Purpose", PURPOSES,
            key="ack_purpose"
        )
    with col2:
        ack_note = st.text_input(
            "Optional note",
            key="ack_note"
        )
        ack_prasadham = st.checkbox(
            "Prasadham will be sent by mail",
            key="ack_prasadham"
        )
    # ── STEP 4: Generate WhatsApp link ───────────────────────────
    if st.button("Generate WhatsApp Acknowledgement", type="primary", key="ack_generate"):
        if not ack_donor_mobile or ack_donor_mobile in ("", "nan"):
            st.error("This donor has no mobile number. Edit the donor above to add one.")
            _render_log()
            return
        purpose_display = (
            f"{ack_purpose} - {ack_note.strip()}" if ack_note.strip() else ack_purpose
        )
        if ack_prasadham:
            closing = "An e-receipt will be sent to you by WhatsApp and Prasadham will be sent by post."
        else:
            closing = "An e-receipt will be sent to you by WhatsApp."
        message_parts = [
            f"Dear {ack_donor_name},",
            f"thank you for your contribution of Rs. {ack_amount:,.2f} for {purpose_display}.",
            closing,
        ]
        message_text = " ".join(message_parts)
        digits = "".join(c for c in ack_donor_mobile if c.isdigit())
        wa_url = f"https://wa.me/{digits}?text={urllib.parse.quote(message_text)}"
        try:
            _save_ack_log({
                "donor_name": ack_donor_name,
                "mobile": ack_donor_mobile,
                "amount": ack_amount,
                "purpose": purpose_display,
                "note": ack_note.strip(),
                "prasadham": ack_prasadham,
                "message": message_text,
                "sent_by": current_user,
            })
            st.success(f"Acknowledgement ready for {ack_donor_name}")
        except Exception as e:
            st.error(f"Could not save to log: {e}")
            _render_log()
            return
        st.session_state["ack_wa_url"] = wa_url
        st.session_state["ack_wa_name"] = ack_donor_name
        st.session_state["ack_message_preview"] = message_text
    # Show WhatsApp button if generated
    if st.session_state.get("ack_wa_url"):
        st.info(f"**Message preview:** {st.session_state['ack_message_preview']}")
        st.link_button(
            f"📲 Send WhatsApp to {st.session_state['ack_wa_name']}",
            st.session_state["ack_wa_url"]
        )
        if st.button("Clear", key="ack_clear"):
            for k in _ACK_WIDGET_KEYS:
                st.session_state.pop(k, None)
            st.rerun()
    # ── Acknowledgement Log ───────────────────────────────────────
    _render_log()
def _render_log():
    st.divider()
    st.subheader("📋 Acknowledgement Log")
    st.caption("Chronological record of all acknowledgements sent.")
    log_search = st.text_input(
        "Search log by WhatsApp number",
        key="ack_log_search",
        placeholder="Enter digits to filter"
    )
    log = _load_ack_log(log_search)
    if not log:
        st.info("No acknowledgements sent yet." if not log_search.strip()
                else "No records found for that number.")
    else:
        for entry in log:
            sent_at = entry.get("sent_at", "")
            try:
                sent_at_fmt = datetime.fromisoformat(str(sent_at)).strftime("%d %b %Y %H:%M")
            except Exception:
                sent_at_fmt = str(sent_at)
            prasadham_tag = " | 📦 Prasadham" if entry.get("prasadham") else ""
            st.write(
                f"**{sent_at_fmt}** | {entry['donor_name']} | "
                f"Rs. {float(entry['amount']):,.2f} | {entry['purpose']} | "
                f"Sent by: {entry['sent_by']}{prasadham_tag}"
            )
