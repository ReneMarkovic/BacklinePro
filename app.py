import streamlit as st
import pandas as pd
import json
from datetime import datetime
from pathlib import Path
from io import BytesIO

# PDF (ReportLab)
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

# ----------------- UI CONFIG -----------------
st.set_page_config(page_title="Gear Booking MVP", page_icon="🎤", layout="wide")
st.title("🎤 Gear Booking MVP (demo)")

# ----------------- DATA I/O -----------------
DATA_PATH = st.sidebar.text_input("Excel path", value="gear_booking_sample.xlsx")

@st.cache_data(show_spinner=False)
def load_data(path: str) -> dict:
    x = Path(path)
    if not x.exists():
        raise FileNotFoundError(f"Excel ni najden: {x.resolve()}")
    xls = pd.ExcelFile(x)
    dfs = {name: pd.read_excel(xls, name) for name in xls.sheet_names}

    # Ensure datetime types on known cols
    if "events" in dfs and not dfs["events"].empty:
        for col in ["start_dt", "end_dt"]:
            if col in dfs["events"].columns:
                dfs["events"][col] = pd.to_datetime(dfs["events"][col])
    if "holds" in dfs and not dfs["holds"].empty:
        for col in ["start_dt", "end_dt"]:
            if col in dfs["holds"].columns:
                dfs["holds"][col] = pd.to_datetime(dfs["holds"][col])
    return dfs

def save_data(path: str, dfs: dict) -> None:
    with pd.ExcelWriter(path, engine="openpyxl", mode="w") as writer:
        for name, df in dfs.items():
            df.to_excel(writer, sheet_name=name, index=False)

# ----------------- CORE UTILS -----------------
def overlap(a_start, a_end, b_start, b_end) -> bool:
    return (a_start < b_end) and (a_end > b_start)

def event_window(start_dt, end_dt, buf_before_min: int, buf_after_min: int):
    return (start_dt - pd.to_timedelta(buf_before_min, unit="m"),
            end_dt + pd.to_timedelta(buf_after_min, unit="m"))

def is_item_available(item_id: int, start_dt, end_dt, buf_before, buf_after, dfs: dict) -> bool:
    s, e = event_window(start_dt, end_dt, buf_before, buf_after)

    # reservations (only HELD/CONFIRMED)
    if "reservations" in dfs and "events" in dfs and not dfs["reservations"].empty and not dfs["events"].empty:
        res = dfs["reservations"].merge(
            dfs["events"], left_on="event_id", right_on="id", suffixes=("_r", "_e")
        )
        res = res[(res["item_id"] == item_id) & (res["status"].isin(["HELD", "CONFIRMED"]))]
        for _, row in res.iterrows():
            s2, e2 = event_window(
                row["start_dt"], row["end_dt"],
                int(row.get("buffer_before_min", 0) or 0),
                int(row.get("buffer_after_min", 0) or 0)
            )
            if overlap(s, e, s2, e2):
                return False

    # holds (service/maintenance)
    if "holds" in dfs and not dfs["holds"].empty:
        holds = dfs["holds"]
        holds = holds[holds["item_id"] == item_id]
        for _, row in holds.iterrows():
            if overlap(s, e, row["start_dt"], row["end_dt"]):
                return False

    # item condition
    if "items" not in dfs or dfs["items"].empty:
        return False
    item_rows = dfs["items"].loc[dfs["items"]["id"] == item_id]
    if item_rows.empty:
        return False
    if str(item_rows.iloc[0]["condition"]).upper() != "OK":
        return False

    return True

def find_items_for_model(model_id: int, qty: int, start_dt, end_dt, buf_before, buf_after, dfs: dict):
    if "items" not in dfs or dfs["items"].empty:
        return []
    candidates = dfs["items"][
        (dfs["items"]["model_id"] == model_id) & (dfs["items"]["condition"] == "OK")
    ].copy()

    chosen = []
    for _, row in candidates.iterrows():
        if is_item_available(int(row["id"]), start_dt, end_dt, buf_before, buf_after, dfs):
            chosen.append(int(row["id"]))
            if len(chosen) >= qty:
                break
    return chosen

def accessories_for_model(model_id: int, count: int, dfs: dict):
    """Returns (required_dict, optional_dict) where keys are model names, values are quantities."""
    if "models" not in dfs or dfs["models"].empty:
        return {}, {}
    model_rows = dfs["models"].loc[dfs["models"]["id"] == model_id]
    if model_rows.empty:
        return {}, {}
    cat_id = int(model_rows.iloc[0]["category_id"])

    rule = dfs["accessory_rules"][dfs["accessory_rules"]["category_id"] == cat_id] if "accessory_rules" in dfs else pd.DataFrame()
    required = {}
    optional = {}
    if not rule.empty:
        r = rule.iloc[0]
        if isinstance(r.get("required_json", ""), str) and r["required_json"].strip():
            req = json.loads(r["required_json"]).get("model_name_to_qty", {})
            required = {name: int(qty) * count for name, qty in req.items()}
        if isinstance(r.get("optional_json", ""), str) and r["optional_json"].strip():
            opt = json.loads(r["optional_json"]).get("model_name_to_qty", {})
            optional = {name: int(qty) * count for name, qty in opt.items()}
    return required, optional

# ----------------- PDF EXPORT -----------------
def generate_cart_pdf(cart: list, title: str = "", start=None, end=None) -> bytes:
    """Build a simple PDF of the cart (and optional title/date/time)."""
    buf = BytesIO()
    doc = SimpleDocTemplate(buf)
    styles = getSampleStyleSheet()
    elems = []

    header = "Košarica – povzetek"
    if title:
        header += f" | {title}"
    elems.append(Paragraph(header, styles["Title"]))

    if start and end:
        elems.append(Paragraph(f"Termin: {start} – {end}", styles["Normal"]))
    elems.append(Spacer(1, 8))

    if not cart:
        elems.append(Paragraph("Košarica je prazna.", styles["Normal"]))
    else:
        data = [["Model", "Količina"]]
        for item in cart:
            data.append([str(item.get("model_name", "")), str(item.get("qty", ""))])

        t = Table(data, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ]))
        elems.append(t)

    doc.build(elems)
    pdf = buf.getvalue()
    buf.close()
    return pdf

# ----------------- STATE -----------------
if "cart" not in st.session_state:
    st.session_state.cart = []  # list of dict: {model_id, model_name, qty}

# ----------------- LOAD DATA -----------------
try:
    dfs = load_data(DATA_PATH)
except Exception as e:
    st.error(f"Napaka pri branju Excela: {e}")
    st.stop()

# ----------------- SIDEBAR: BOOKING FORM -----------------
with st.sidebar:
    st.header("🗓️ Nova rezervacija")
    title = st.text_input("Naziv dogodka", value="Demo dogodek")

    col1, col2 = st.columns(2)
    with col1:
        start_dt = st.date_input("Začetni datum")
        start_tm = st.time_input("Začetni čas", value=None)
    with col2:
        end_dt = st.date_input("Končni datum", value=None)
        end_tm = st.time_input("Končni čas", value=None)

    buf_before = st.number_input("Buffer pred (min)", min_value=0, value=60, step=15)
    buf_after  = st.number_input("Buffer po (min)", min_value=0, value=60, step=15)

    # Export PDF button (works even without times)
    if st.session_state.cart:
        _start = datetime.combine(start_dt, start_tm) if (start_tm is not None and end_tm is not None and end_dt is not None) else None
        _end   = datetime.combine(end_dt, end_tm)     if (start_tm is not None and end_tm is not None and end_dt is not None) else None
        pdf_bytes = generate_cart_pdf(st.session_state.cart, title=title, start=_start, end=_end)
        st.download_button(
            label="📄 Izvozi košarico v PDF",
            data=pdf_bytes,
            file_name="kosarica.pdf",
            mime="application/pdf"
        )

    if start_tm is None or end_tm is None or end_dt is None:
        st.info("Izberi datume in čase.")
    else:
        start = datetime.combine(start_dt, start_tm)
        end = datetime.combine(end_dt, end_tm)

        st.subheader("Dodaj opremo")

        # Kategorije
        if "categories" not in dfs or dfs["categories"].empty:
            st.error("V Excelu ni definiranih kategorij (list 'categories').")
            st.stop()
        cat_names = dfs["categories"]["name"].tolist()
        cat_choice = st.selectbox("Kategorija", options=cat_names)
        cat_id = int(dfs["categories"].loc[dfs["categories"]["name"] == cat_choice, "id"].iloc[0])

        # Modeli v izbrani kategoriji (BREZ merge; robustno)
        if "models" not in dfs or dfs["models"].empty:
            st.error("V Excelu ni definiranih modelov (list 'models').")
            st.stop()
        models_df = dfs["models"].loc[dfs["models"]["category_id"] == cat_id].copy()
        if models_df.empty:
            st.warning("V izbrani kategoriji ni modelov.")
            st.stop()

        # brand_id -> brand_name
        brand_map = dfs["brands"].set_index("id")["name"] if "brands" in dfs and not dfs["brands"].empty else pd.Series(dtype=str)
        models_df["brand_name"] = models_df["brand_id"].map(brand_map).fillna("")
        models_df["label"] = models_df.apply(
            lambda r: f'{r["name"]} [{r["brand_name"]}]' if r["brand_name"] else r["name"],
            axis=1
        )

        model_label = st.selectbox("Model", options=models_df["label"].tolist())
        selected = models_df.loc[models_df["label"] == model_label]
        if selected.empty:
            st.error("Izbranega modela ni mogoče najti.")
            st.stop()
        selected = selected.iloc[0]
        model_id = int(selected["id"])
        model_name = str(selected["name"])

        qty = st.number_input("Količina", min_value=1, value=1, step=1)
        if st.button("➕ Dodaj v košarico"):
            st.session_state.cart.append({"model_id": model_id, "model_name": model_name, "qty": int(qty)})

        if st.session_state.cart:
            st.write("**Košarica:**")
            st.dataframe(pd.DataFrame(st.session_state.cart))

        if st.button("🧮 Izračun ponudbe"):
            results = []
            accessories_need = {}
            for item in st.session_state.cart:
                chosen = find_items_for_model(item["model_id"], item["qty"], start, end, buf_before, buf_after, dfs)
                results.append({
                    "model": item["model_name"],
                    "requested": item["qty"],
                    "assigned": len(chosen),
                    "item_ids": chosen
                })

                req, _opt = accessories_for_model(item["model_id"], item["qty"], dfs)
                for name, q in req.items():
                    accessories_need[name] = accessories_need.get(name, 0) + q

            st.session_state.quote = {
                "results": results,
                "accessories_need": accessories_need,
                "start": start,
                "end": end,
                "buf_before": buf_before,
                "buf_after": buf_after,
                "title": title
            }

# ----------------- MAIN: INVENTAR & QUOTE -----------------
st.subheader("📦 Inventar (primer)")
if "items" in dfs and not dfs["items"].empty and "models" in dfs and not dfs["models"].empty:
    # Prikaz: items + model (brez KeyError na 'id')
    models_view = dfs["models"][["id", "name"]].rename(columns={"id": "model_id", "name": "model"})
    inv = dfs["items"].merge(models_view, on="model_id", how="left")
    inv = inv.rename(columns={"id": "item_id"})
    st.dataframe(inv)
else:
    st.info("Ni artiklov v listu 'items' ali modelov v listu 'models'.")

if "quote" in st.session_state:
    st.markdown("### ✅ Rezultat – razpoložljivost")
    st.dataframe(pd.DataFrame(st.session_state["quote"]["results"]))

    # Dodatki (required)
    need = st.session_state["quote"]["accessories_need"]
    if need:
        st.markdown("### 🔌 Predlagani dodatki (required)")
        acc_rows = []
        for model_name, qty in need.items():
            m_id = dfs["models"].loc[dfs["models"]["name"] == model_name, "id"]
            if not m_id.empty:
                m_id = int(m_id.iloc[0])
                chosen = find_items_for_model(
                    m_id, qty,
                    st.session_state["quote"]["start"],
                    st.session_state["quote"]["end"],
                    st.session_state["quote"]["buf_before"],
                    st.session_state["quote"]["buf_after"],
                    dfs
                )
                acc_rows.append({"model": model_name, "requested": qty, "assigned": len(chosen), "item_ids": chosen})
            else:
                acc_rows.append({"model": model_name, "requested": qty, "assigned": 0, "item_ids": []})
        st.dataframe(pd.DataFrame(acc_rows))
        st.caption("Če je 'assigned' < 'requested', manjka dodatkov – dodaj alternative ali zmanjša količino.")

    # Potrditev: zapiši event + reservations
    if st.button("💾 Potrdi in zapiši rezervacijo v Excel"):
        dfs_local = load_data(DATA_PATH)  # reload fresh

        # nov event id
        new_eid = (dfs_local["events"]["id"].max() if ("events" in dfs_local and not dfs_local["events"].empty) else 0) + 1
        start = st.session_state["quote"]["start"]
        end = st.session_state["quote"]["end"]
        buf_before = int(st.session_state["quote"]["buf_before"])
        buf_after = int(st.session_state["quote"]["buf_after"])

        new_event = pd.DataFrame([{
            "id": new_eid,
            "title": st.session_state["quote"]["title"],
            "start_dt": start,
            "end_dt": end,
            "buffer_before_min": buf_before,
            "buffer_after_min": buf_after,
            "location": "",
            "contact_name": "",
            "contact_phone": "",
            "notes": ""
        }])

        if "events" not in dfs_local or dfs_local["events"].empty:
            dfs_local["events"] = new_event
        else:
            dfs_local["events"] = pd.concat([dfs_local["events"], new_event], ignore_index=True)

        # rezervacije iz results + accessories
        to_assign = []
        for row in st.session_state["quote"]["results"]:
            for iid in row["item_ids"]:
                to_assign.append(iid)
        for model_name, qty in st.session_state["quote"]["accessories_need"].items():
            m_id = dfs_local["models"].loc[dfs_local["models"]["name"] == model_name, "id"]
            if not m_id.empty:
                m_id = int(m_id.iloc[0])
                for iid in find_items_for_model(m_id, qty, start, end, buf_before, buf_after, dfs_local):
                    to_assign.append(iid)

        if to_assign:
            next_id = (dfs_local["reservations"]["id"].max() if ("reservations" in dfs_local and not dfs_local["reservations"].empty) else 0) + 1
            rows = [{
                "id": next_id + i,
                "event_id": new_eid,
                "item_id": iid,
                "status": "CONFIRMED",
                "created_at": datetime.now()
            } for i, iid in enumerate(to_assign)]

            if "reservations" not in dfs_local or dfs_local["reservations"].empty:
                dfs_local["reservations"] = pd.DataFrame(rows)
            else:
                dfs_local["reservations"] = pd.concat([dfs_local["reservations"], pd.DataFrame(rows)], ignore_index=True)

        save_data(DATA_PATH, dfs_local)
        st.success("Rezervacija zapisana.")

        # počisti stanje za nov vnos
        st.session_state.cart = []
        if "quote" in st.session_state:
            del st.session_state["quote"]

        st.balloons()

st.markdown("---")
st.caption("Demo: kategorije, modeli, artikli, dogodki, rezervacije, servisni 'holds' in pravilo dodatkov (mikrofoni → XLR + stojalo).")
