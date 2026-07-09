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


# ── DB helpers (use same Neon connection from session_state) ──────────────

def _get_conn():
    """Reuse existing Neon connection from session state."""
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


# ── Main render function ───────────────────────────────────────────────────

def render_whatsapp_ack_section(donors, current_user: str):
    """
    Call this at the bottom of app.py to render the WhatsApp
    Acknowledgement section. Requires the donors DataFrame
    already loaded by app.py and the logged-in username.
    """

    st.divider()
    st.subheader("📲 WhatsApp Acknowledgement")
    st.caption(
        "Select a donor, enter the amount and purpose they informed you about, "
        "then generate a WhatsApp acknowledgement link to send them."
    )

    # ── Donor dropdown ────────────────────────────────────────────
    if donors.empty:
        st.warning("No donors found. Add a donor in the section above first.")
        return

    donor_options = [
        r["NAME"] if not r["Mobile Number"] or r["Mobile Number"] in ("", "nan")
        else f"{r['NAME']} - {r['Mobile Number']}"
        for _, r in donors.iterrows()
    ]

    ack_selected = st.selectbox(
        "Select donor",
        options=["-- Select donor --"] + donor_options,
        key="ack_donor_select"
    )

    if ack_selected == "-- Select donor --":
        return

    ack_index = donors.index[donor_options.index(ack_selected)]
    ack_donor_name = donors.loc[ack_index, "NAME"]
    ack_donor_mobile = str(donors.loc[ack_index, "Mobile Number"])

    # ── Form fields ───────────────────────────────────────────────
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

    # ── Generate WhatsApp link ────────────────────────────────────
    if st.button("Generate WhatsApp Acknowledgement", type="primary", key="ack_generate"):

        if not ack_donor_mobile or ack_donor_mobile in ("", "nan"):
            st.error("This donor has no mobile number. Edit the donor above to add one.")
            return

        # Build message
        purpose_display = (
            f"{ack_purpose} - {ack_note.strip()}" if ack_note.strip() else ack_purpose
        )
        message_parts = [
            f"Dear {ack_donor_name},",
            f"thank you for your contribution of Rs. {ack_amount:,.2f} for {purpose_display}.",
            "An e-receipt will be sent to you by WhatsApp upon receiving bank statement.",
        ]
        if ack_prasadham:
            message_parts.append("Prasadham will be sent by mail.")

        message_text = " ".join(message_parts)

        # WhatsApp link
        digits = "".join(c for c in ack_donor_mobile if c.isdigit())
        wa_url = f"https://wa.me/{digits}?text={urllib.parse.quote(message_text)}"

        # Save to log
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
            return

        # Store in session so button stays visible after rerun
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
            for k in ["ack_wa_url", "ack_wa_name", "ack_message_preview"]:
                st.session_state.pop(k, None)
            st.rerun()

    # ── Acknowledgement Log ───────────────────────────────────────
    st.divider()
    st.subheader("📋 Acknowledgement Log")

    search_mob = st.text_input(
        "Search by WhatsApp number",
        key="ack_log_search",
        placeholder="Enter digits to filter"
    )

    log = _load_ack_log(search_mob)

    if not log:
        st.info("No acknowledgements sent yet." if not search_mob.strip()
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
