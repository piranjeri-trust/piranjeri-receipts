import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import json
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

from receipt_core import generate_receipt_pdf

# ---------------- LOGIN CONFIG ----------------
USERS = {
    "esrivasan": "Password1",
    "pmk45in":   "Password2",
    "admin3":    "Password3"
}
SESSION_TIMEOUT = 60  # minutes

# ---------------- LOCAL PATHS (PDF only) ----------------
BASE_DIR = Path(__file__).resolve().parent
OUT_DIR  = BASE_DIR / "generated_receipts"
OM_PATH  = BASE_DIR / "om_saffron.png"
OUT_DIR.mkdir(exist_ok=True)

PURPOSES = [
    "Nithya Pooja","Garuda Seva","Pradhosham","Sangabhishekam",
    "Panguni uthiram","Annadhanam","Kumbhabhishekam","Varushabhishekam",
    "Temple Renovation","General Donation"
]
COUNTRY_CODES = {
    "India (+91)":"91","Singapore (+65)":"65","Malaysia (+60)":"60",
    "UAE (+971)":"971","Oman (+968)":"968","UK (+44)":"44","USA (+1)":"1"
}

# ================================================================
# SUPABASE REST API HELPERS
# ================================================================
def _sb():
    url = "https://qjezqsubigijpfkecrqn.supabase.co"
    key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFqZXpxc3ViaWdpanBma2VjcnFuIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NzIzMTQ4NiwiZXhwIjoyMDkyODA3NDg2fQ.Q2Gupt_vrqmpBZVUDtnmltt96FKQWQTVL6gSh7iYFRA"
    hdrs = {
        "apikey":        key,
        "Authorization": f"Bearer {key}",
        "Content-Type":  "application/json",
        "Prefer":        "return=representation",
    }
    return url, hdrs

def sb_get(table, qs=""):
    url, h = _sb()
    req = urllib.request.Request(f"{url}/rest/v1/{table}?{qs}", headers=h)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())

def sb_post(table, data):
    url, h = _sb()
    req = urllib.request.Request(
        f"{url}/rest/v1/{table}",
        data=json.dumps(data).encode(), headers=h, method="POST"
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())

def sb_patch(table, col, val, data):
    url, h = _sb()
    req = urllib.request.Request(
        f"{url}/rest/v1/{table}?{col}=eq.{urllib.parse.quote(str(val))}",
        data=json.dumps(data).encode(), headers=h, method="PATCH"
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())

# ================================================================
# LOGIN
# ================================================================
def login():
    st.title("Piranjeri Temple Receipt Generator")
    st.subheader("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login", type="primary"):
        if username in USERS and USERS[username] == password:
            st.session_state["user"]       = username
            st.session_state["login_time"] = datetime.now().isoformat()
            st.rerun()
        else:
            st.error("Invalid credentials")

def check_session():
    if "login_time" in st.session_state:
        if datetime.now() - datetime.fromisoformat(st.session_state["login_time"]) \
                > timedelta(minutes=SESSION_TIMEOUT):
            st.session_state.clear()
            st.warning("Session expired. Please login again.")
            st.rerun()

# ================================================================
# SERIAL (Supabase)
# ================================================================
def get_serial(issue_date):
    fy   = issue_date.year if issue_date.month >= 4 else issue_date.year - 1
    rows = sb_get("serial_counter", f"fy=eq.{fy}")
    if rows:
        new_count = rows[0]["count"] + 1
        sb_patch("serial_counter", "fy", fy, {"count": new_count})
    else:
        new_count = 1
        sb_post("serial_counter", {"fy": fy, "count": 1})
    return f"{new_count:03d}/{fy}"

def reset_serial(fy, start_from):
    rows = sb_get("serial_counter", f"fy=eq.{fy}")
    if rows:
        sb_patch("serial_counter", "fy", fy, {"count": start_from})
    else:
        sb_post("serial_counter", {"fy": fy, "count": start_from})

# ================================================================
# DONORS (Supabase)
# ================================================================
def load_donors():
    try:
        rows = sb_get("donors", "order=name.asc")
        if not rows:
            return pd.DataFrame(columns=["NAME","Mobile Number"])
        df = pd.DataFrame([{"NAME": r["name"], "Mobile Number": r.get("mobile","")} for r in rows])
        df["Mobile Number"] = df["Mobile Number"].fillna("").astype(str)
        return df
    except Exception as e:
        st.error(f"Could not load donors: {e}")
        return pd.DataFrame(columns=["NAME","Mobile Number"])

def add_donor(name, mobile):
    sb_post("donors", {"name": name, "mobile": mobile})

def edit_donor(old_name, old_mobile, new_name, new_mobile):
    rows = sb_get("donors",
        f"name=eq.{urllib.parse.quote(old_name)}&mobile=eq.{urllib.parse.quote(old_mobile)}")
    if rows:
        sb_patch("donors", "id", rows[0]["id"], {"name": new_name, "mobile": new_mobile})

def normalize_mobile(m):
    return "".join(c for c in str(m) if c.isdigit())

# ================================================================
# RECEIPTS (Supabase)
# ================================================================
def save_receipt(record):
    sb_post("receipts", {
        "serial":        record["serial"],
        "name":          record["name"],
        "mobile":        record.get("mobile",""),
        "amount":        float(record["amount"]),
        "purpose":       record.get("purpose",""),
        "payment":       record.get("payment",""),
        "cheque_number": record.get("cheque_number",""),
        "issue_date":    record["issue_date"],
        "credit_date":   record.get("credit_date",""),
        "issued_by":     record.get("user",""),
        "pdf_file":      record.get("pdf_file",""),
        "status":        "ACTIVE",
    })

def load_history():
    try:
        rows = sb_get("receipts", "order=issue_date.desc,serial.desc")
        for r in rows:
            r["user"]    = r.get("issued_by","")
            r["status"]  = r.get("status","ACTIVE")
        return rows
    except Exception as e:
        st.error(f"Could not load receipts: {e}")
        return []

def cancel_receipt(serial, cancelled_by, reason):
    sb_patch("receipts", "serial", serial, {
        "status":        "CANCELLED",
        "cancelled_by":  cancelled_by,
        "cancelled_at":  datetime.now().isoformat(),
        "cancel_reason": reason,
    })

# ================================================================
# APP
# ================================================================
if "user" not in st.session_state:
    login()
    st.stop()

check_session()

st.title("Piranjeri Temple Receipt Generator")
st.caption(f"Logged in as: {st.session_state['user']}")

if st.button("Logout"):
    st.session_state.clear()
    st.rerun()

donors = load_donors()

# ── Select donor ─────────────────────────────────────────────────
if donors.empty:
    st.warning("No donor found. Add one below.")
    selected = selected_index = None
else:
    donor_options = [
        r['NAME'] if not r['Mobile Number'] or r['Mobile Number'] in ('','nan')
        else f"{r['NAME']} - {r['Mobile Number']}"
        for _, r in donors.iterrows()
    ]
    selected       = st.selectbox("Select donor", donor_options)
    selected_index = donors.index[donor_options.index(selected)]

# ── Add donor ─────────────────────────────────────────────────────
with st.expander("Add New Donor"):
    new_name    = st.text_input("New donor name")
    new_country = st.selectbox("Country code", list(COUNTRY_CODES.keys()), key="add_country")
    new_mobile  = st.text_input("New donor mobile number (without country code) — optional")
    if st.button("Save New Donor"):
        nm = new_name.strip()
        if not nm:
            st.error("Donor name is required.")
        else:
            raw = normalize_mobile(new_mobile)
            mm  = (COUNTRY_CODES[new_country] + raw) if raw else ""
            dup = donors[donors["NAME"].str.lower() == nm.lower()] if not mm else \
                  donors[(donors["NAME"].str.lower()==nm.lower()) &
                         (donors["Mobile Number"].astype(str)==mm)]
            if not dup.empty:
                st.warning("This donor already exists.")
            else:
                add_donor(nm, mm)
                st.success("New donor added.")
                st.rerun()

# ── Edit donor ────────────────────────────────────────────────────
if selected is not None:
    with st.expander("Edit Selected Donor"):
        cur_name   = donors.loc[selected_index, "NAME"]
        cur_mobile = str(donors.loc[selected_index, "Mobile Number"])
        def_country, def_local = "India (+91)", cur_mobile
        for label, code in COUNTRY_CODES.items():
            if cur_mobile.startswith(code):
                def_country, def_local = label, cur_mobile[len(code):]
                break
        edit_name    = st.text_input("Edit donor name", value=cur_name)
        edit_country = st.selectbox("Edit country code", list(COUNTRY_CODES.keys()),
                                    index=list(COUNTRY_CODES.keys()).index(def_country),
                                    key="edit_country")
        edit_mobile  = st.text_input("Edit mobile (without country code) — optional",
                                     value=def_local)
        if st.button("Update Donor"):
            en = edit_name.strip()
            if not en:
                st.error("Name cannot be empty.")
            else:
                raw = normalize_mobile(edit_mobile)
                em  = (COUNTRY_CODES[edit_country] + raw) if raw else ""
                edit_donor(cur_name, cur_mobile, en, em)
                st.success("Donor updated.")
                st.rerun()

# ── Receipt form ──────────────────────────────────────────────────
if selected is not None:
    donor_name   = donors.loc[selected_index, "NAME"]
    donor_mobile = str(donors.loc[selected_index, "Mobile Number"])

    c1, c2 = st.columns(2)
    with c1:
        amount         = st.number_input("Amount received (Rs.)", min_value=1.0, step=1.0, format="%.2f")
        payment_method = st.selectbox("Payment method", ["cash","cheque","bank_transfer"])
        credit_date    = st.date_input("Date of credit into trust bank account", value=datetime.today())
    with c2:
        issue_date    = st.date_input("Receipt issue date", value=datetime.today())
        purpose       = st.selectbox("Purpose", PURPOSES)
        optional_note = st.text_input("Optional note")

    cheque_number = ""
    if payment_method == "cheque":
        cheque_number = st.text_input("Cheque number")

    if st.button("Generate Receipt", type="primary"):
        final_purpose  = f"{purpose} - {optional_note.strip()}" if optional_note.strip() else purpose
        receipt_number = get_serial(issue_date)
        safe_name      = "".join(c for c in donor_name if c.isalnum() or c in " _-").strip().replace(" ","_")
        out_file       = OUT_DIR / f"{receipt_number.replace('/','_')}_{safe_name}.pdf"

        generate_receipt_pdf(
            output_path=out_file, donor_name=donor_name, donor_mobile=donor_mobile,
            amount=float(amount), credit_date=credit_date.strftime("%Y-%m-%d"),
            issue_date=issue_date.strftime("%Y-%m-%d"), receipt_for=final_purpose,
            counter_path=BASE_DIR/"serial_counter.json", om_image_path=OM_PATH,
            payment_method=payment_method, cheque_number=cheque_number,
            receipt_number_override=receipt_number,
        )

        save_receipt({
            "serial": receipt_number, "name": donor_name, "mobile": donor_mobile,
            "amount": float(amount), "purpose": final_purpose, "payment": payment_method,
            "cheque_number": cheque_number, "issue_date": issue_date.strftime("%Y-%m-%d"),
            "credit_date": credit_date.strftime("%Y-%m-%d"), "user": st.session_state["user"],
            "pdf_file": out_file.name,
        })

        st.success(f"Receipt generated: {receipt_number}")
        with open(out_file,"rb") as f:
            st.session_state["receipt_bytes"]    = f.read()
        st.session_state["receipt_filename"]     = out_file.name
        st.session_state["receipt_whatsapp_url"] = (
            f"https://wa.me/{normalize_mobile(donor_mobile)}"
            f"?text=%E0%AE%A8%E0%AE%AE%E0%AE%B8%E0%AF%8D%E0%AE%95%E0%AE%BE%E0%AE%B0%E0%AE%AE%E0%AF%8D%20%21%20"
            f"{donor_name.replace(' ','%20')}%2C%20your%20donation%20receipt%20"
            f"%28{receipt_number.replace('/','%2F')}%29%20from%20Piranjeri%20Temples%20Family%20Trust%20is%20attached%2C%20thank%20you."
        )

    if st.session_state.get("receipt_bytes"):
        st.download_button("⬇️ Download PDF", st.session_state["receipt_bytes"],
                           file_name=st.session_state["receipt_filename"],
                           mime="application/pdf", key="dl_receipt")
        st.markdown(f"[📲 Open WhatsApp chat]({st.session_state['receipt_whatsapp_url']})")

# ── Receipt history ───────────────────────────────────────────────
st.subheader("Receipt History")
history = load_history()

if not history:
    st.info("No receipts generated yet.")
else:
    from collections import defaultdict
    grouped = defaultdict(list)
    for h in history:
        try:    key = datetime.strptime(h["issue_date"],"%Y-%m-%d").strftime("%B %Y")
        except: key = "Unknown"
        grouped[key].append(h)

    for month_label in sorted(grouped.keys(), reverse=True):
        entries = grouped[month_label]
        with st.expander(f"📁 {month_label}  ({len(entries)} receipts)"):
            for h in sorted(entries, key=lambda x: x["serial"], reverse=True):
                if h.get("status") == "CANCELLED":
                    st.markdown(
                        f"~~{h['serial']}~~ | {h['name']} | Rs.{h['amount']} | "
                        f"{h['purpose']} | {h['payment']} | "
                        f"❌ CANCELLED by {h.get('cancelled_by','')} — {h.get('cancel_reason','')}"
                    )
                else:
                    st.write(f"{h['serial']} | {h['name']} | Rs.{h['amount']} | "
                             f"{h['purpose']} | {h['payment']} | {h.get('user','')}")

# ── Reprint / Cancel ──────────────────────────────────────────────
st.subheader("Reprint / Cancel Receipt")
sc1, sc2, sc3 = st.columns(3)
with sc1: srn = st.text_input("Search by Receipt Number")
with sc2: smb = st.text_input("Search by Mobile Number")
with sc3:
    date_on = st.checkbox("Filter by Issue Date")
    sdt     = st.date_input("Select Issue Date", value=datetime.today()) if date_on else None

fh = history
if srn.strip(): fh = [h for h in fh if srn.strip().lower() in str(h.get("serial","")).lower()]
if smb.strip():
    mq = normalize_mobile(smb)
    fh = [h for h in fh if mq in normalize_mobile(str(h.get("mobile","")))]
if sdt:
    iq = sdt.strftime("%Y-%m-%d")
    fh = [h for h in fh if str(h.get("issue_date","")) == iq]

if srn.strip() or smb.strip() or date_on:
    if fh:
        for i, h in enumerate(fh[::-1]):
            st.divider()
            if h.get("status") == "CANCELLED":
                st.markdown(
                    f"~~{h['serial']}~~ | {h['name']} | Rs.{h['amount']} | "
                    f"{h['purpose']} | ❌ **CANCELLED** by {h.get('cancelled_by','')} "
                    f"— _{h.get('cancel_reason','')}_"
                )
            else:
                st.write(f"{h['serial']} | {h['name']} | Rs.{h['amount']} | {h['purpose']} | {h['payment']}")
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("🖨️ Reprint", key=f"rp_{i}_{h['serial']}"):
                        out_file = OUT_DIR / h["pdf_file"]
                        generate_receipt_pdf(
                            output_path=out_file, donor_name=h["name"], donor_mobile=h["mobile"],
                            amount=float(h["amount"]), credit_date=h["credit_date"],
                            issue_date=h["issue_date"], receipt_for=h["purpose"],
                            counter_path=BASE_DIR/"serial_counter.json", om_image_path=OM_PATH,
                            payment_method=h["payment"], cheque_number=h.get("cheque_number",""),
                            receipt_number_override=h["serial"],
                        )
                        st.success(f"Reprinted {h['serial']}")
                        with open(out_file,"rb") as f:
                            st.download_button(f"⬇️ Download {h['serial']}", f.read(),
                                               file_name=out_file.name, mime="application/pdf",
                                               key=f"dlrp_{i}_{h['serial']}")
                with b2:
                    if st.button("❌ Cancel", key=f"cx_{i}_{h['serial']}"):
                        st.session_state[f"cc_{h['serial']}"] = True

            if st.session_state.get(f"cc_{h['serial']}", False):
                st.warning(f"Cancel {h['serial']} — {h['name']} — Rs.{h['amount']}?")
                cr = st.text_input("Reason (required)", key=f"cr_{h['serial']}")
                cy, cn = st.columns(2)
                with cy:
                    if st.button("Confirm Cancel", key=f"ccy_{h['serial']}"):
                        if not cr.strip():
                            st.error("Please enter a reason.")
                        else:
                            cancel_receipt(h["serial"], st.session_state["user"], cr.strip())
                            try:
                                from receipt_core import generate_cancelled_pdf
                                cf_out = OUT_DIR / f"CANCELLED_{h['pdf_file']}"
                                generate_cancelled_pdf(
                                    original_path=OUT_DIR/h["pdf_file"], output_path=cf_out,
                                    cancelled_by=st.session_state["user"], reason=cr.strip(),
                                    cancelled_at=datetime.now().isoformat()
                                )
                                st.session_state[f"cfile_{h['serial']}"] = str(cf_out)
                            except Exception:
                                pass
                            st.session_state.pop(f"cc_{h['serial']}", None)
                            st.rerun()
                with cn:
                    if st.button("No, go back", key=f"ccn_{h['serial']}"):
                        st.session_state.pop(f"cc_{h['serial']}", None)
                        st.rerun()

            if st.session_state.get(f"cfile_{h['serial']}"):
                cf = Path(st.session_state[f"cfile_{h['serial']}"])
                if cf.exists():
                    with open(cf,"rb") as f:
                        st.download_button("⬇️ Download Cancelled Receipt", f.read(),
                                           file_name=cf.name, mime="application/pdf",
                                           key=f"dlcf_{h['serial']}")
    else:
        st.warning("No matching receipt found.")

# ── Collections report ────────────────────────────────────────────
st.subheader("📊 Collections Report")

if not history:
    st.info("No receipts yet.")
else:
    from collections import defaultdict
    from generate_report import generate_collections_report

    active_h    = [h for h in history if h.get("status","ACTIVE") != "CANCELLED"]
    cancelled_h = [h for h in history if h.get("status","ACTIVE") == "CANCELLED"]

    all_months = sorted(set(
        datetime.strptime(h["issue_date"],"%Y-%m-%d").strftime("%B %Y")
        for h in history if h.get("issue_date")
    ), reverse=True)

    if all_months:
        sel_month = st.selectbox("Select month to generate report", all_months)

        m_active    = [h for h in active_h
                       if datetime.strptime(h["issue_date"],"%Y-%m-%d").strftime("%B %Y")==sel_month]
        m_cancelled = [h for h in cancelled_h
                       if datetime.strptime(h["issue_date"],"%Y-%m-%d").strftime("%B %Y")==sel_month]

        t_active    = sum(float(h["amount"]) for h in m_active)
        t_cancelled = sum(float(h["amount"]) for h in m_cancelled)

        m1,m2,m3,m4 = st.columns(4)
        m1.metric("Active Receipts",    len(m_active))
        m2.metric("Total Collected",    f"Rs. {t_active:,.2f}")
        m3.metric("Cancelled Receipts", len(m_cancelled))
        m4.metric("Cancelled Amount",   f"Rs. {t_cancelled:,.2f}")

        if st.button("📥 Generate & Download Excel Report", type="primary"):
            REPORTS_DIR = BASE_DIR/"reports"
            REPORTS_DIR.mkdir(exist_ok=True)
            rpt_file = REPORTS_DIR/f"Collections_{sel_month.replace(' ','_')}.xlsx"
            generate_collections_report(
                month_data=m_active, month_label=sel_month,
                output_path=rpt_file, cancelled_data=m_cancelled,
            )
            with open(rpt_file,"rb") as f:
                st.session_state["report_bytes"] = f.read()
            st.session_state["report_filename"]        = rpt_file.name
            st.session_state["report_month"]           = sel_month
            st.session_state["report_count"]           = len(m_active)
            st.session_state["report_cancelled_count"] = len(m_cancelled)

        if st.session_state.get("report_bytes"):
            st.download_button(
                f"⬇️ Download {st.session_state['report_month']} Report",
                st.session_state["report_bytes"],
                file_name=st.session_state["report_filename"],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="rpt_dl"
            )
            st.success(
                f"✅ {st.session_state['report_count']} active + "
                f"{st.session_state.get('report_cancelled_count',0)} cancelled — "
                f"{st.session_state['report_month']}"
            )

    # ── Full Year Report ──────────────────────────────────────────
    st.divider()
    st.subheader("📅 Full Year Report")

    # Determine available financial years from history
    available_years = sorted(set(
        datetime.strptime(h["issue_date"], "%Y-%m-%d").year
        for h in history if h.get("issue_date")
    ), reverse=True)

    if available_years:
        selected_fy = st.selectbox(
            "Select year for full report",
            available_years,
            format_func=lambda y: f"{y}"
        )

        if st.button("📥 Generate Full Year Report", type="primary"):
            # Filter history for selected year
            year_history = [
                h for h in history
                if datetime.strptime(h["issue_date"], "%Y-%m-%d").year == selected_fy
            ]

            REPORTS_DIR = BASE_DIR / "reports"
            REPORTS_DIR.mkdir(exist_ok=True)
            annual_file = REPORTS_DIR / f"Annual_Report_{selected_fy}.xlsx"

            from generate_report import generate_annual_report
            generate_annual_report(
                all_history=year_history,
                financial_year=selected_fy,
                output_path=annual_file,
            )

            with open(annual_file, "rb") as f:
                st.session_state["annual_bytes"]    = f.read()
            st.session_state["annual_filename"]     = annual_file.name
            st.session_state["annual_year"]         = selected_fy

        if st.session_state.get("annual_bytes"):
            st.download_button(
                f"⬇️ Download Full Year {st.session_state['annual_year']} Report",
                st.session_state["annual_bytes"],
                file_name=st.session_state["annual_filename"],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="annual_dl"
            )
            st.success(
                f"✅ Full year {st.session_state['annual_year']} report ready — "
                f"one sheet per month + Summary + Cancelled sheets"
            )

# ── Admin panel ───────────────────────────────────────────────────
if st.session_state.get("user") == "admin3":
    st.subheader("🔧 Admin Panel")

    with st.expander("Reset Serial Counter"):
        st.warning("⚠️ Only reset at start of new financial year or if counter is wrong.")
        ry = st.number_input("Financial Year",  value=datetime.now().year, step=1, format="%d")
        rc = st.number_input("Start from (next receipt = this + 1)", value=0, step=1, format="%d")
        if st.button("Reset Counter", type="primary"):
            reset_serial(int(ry), int(rc))
            st.success(f"✅ Counter reset. Next receipt: {int(rc)+1:03d}/{int(ry)}")

    with st.expander("🔍 Database Connection Test"):
        if st.button("Test Supabase connection"):
            try:
                sb_get("serial_counter", "limit=1")
                st.success("✅ Supabase connected — database is live and permanent.")
            except Exception as e:
                st.error(f"❌ Connection failed: {e}")
