
import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
from pathlib import Path

st.set_page_config(page_title="Gear Booking MVP", page_icon="🎤", layout="wide")
st.title("🎤 Gear Booking MVP (demo)")

# ---- Config ----
DATA_PATH = st.sidebar.text_input("Excel path", value="gear_booking_sample.xlsx")

@st.cache_data(show_spinner=False)
def load_data(path):
    xls = pd.ExcelFile(path)
    dfs = {name: pd.read_excel(xls, name) for name in xls.sheet_names}
    # Ensure datetime types
    if "events" in dfs:
        for col in ["start_dt", "end_dt"]:
            dfs["events"][col] = pd.to_datetime(dfs["events"][col])
    if "holds" in dfs:
        for col in ["start_dt", "end_dt"]:
            dfs["holds"][col] = pd.to_datetime(dfs["holds"][col])
    return dfs

def save_data(path, dfs):
    with pd.ExcelWriter(path, engine="openpyxl", mode="w") as writer:
        for name, df in dfs.items():
            df.to_excel(writer, sheet_name=name, index=False)

def overlap(a_start, a_end, b_start, b_end):
    return (a_start < b_end) and (a_end > b_start)

def event_window(start_dt, end_dt, buf_before_min, buf_after_min):
    return start_dt - pd.to_timedelta(buf_before_min, unit="m"), end_dt + pd.to_timedelta(buf_after_min, unit="m")

def is_item_available(item_id, start_dt, end_dt, buf_before, buf_after, dfs):
    s, e = event_window(start_dt, end_dt, buf_before, buf_after)
    # reservations
    res = dfs["reservations"].merge(dfs["events"], left_on="event_id", right_on="id", suffixes=("_r","_e"))
    res = res[res["item_id"] == item_id]
    res = res[res["status"].isin(["HELD","CONFIRMED"])]
    for _, row in res.iterrows():
        s2, e2 = event_window(row["start_dt"], row["end_dt"], row.get("buffer_before_min",0), row.get("buffer_after_min",0))
        if overlap(s, e, s2, e2):
            return False
    # holds
    holds = dfs["holds"]
    holds = holds[holds["item_id"] == item_id]
    for _, row in holds.iterrows():
        if overlap(s, e, row["start_dt"], row["end_dt"]):
            return False
    # condition
    item = dfs["items"].loc[dfs["items"]["id"]==item_id].iloc[0]
    if item["condition"] != "OK":
        return False
    return True

def find_items_for_model(model_id, qty, start_dt, end_dt, buf_before, buf_after, dfs):
    candidates = dfs["items"][ (dfs["items"]["model_id"]==model_id) & (dfs["items"]["condition"]=="OK") ].copy()
    chosen = []
    for _, row in candidates.iterrows():
        if is_item_available(row["id"], start_dt, end_dt, buf_before, buf_after, dfs):
            chosen.append(int(row["id"]))
            if len(chosen) >= qty:
                break
    return chosen

def get_model_id_by_name(name, dfs):
    m = dfs["models"].loc[dfs["models"]["name"]==name]
    if m.empty:
        return None
    return int(m.iloc[0]["id"])

def accessories_for_model(model_id, count, dfs):
    # rule at category level
    model = dfs["models"].loc[dfs["models"]["id"]==model_id].iloc[0]
    cat_id = int(model["category_id"])
    rule = dfs["accessory_rules"][ dfs["accessory_rules"]["category_id"]==cat_id ]
    required = {}
    optional = {}
    if not rule.empty:
        r = rule.iloc[0]
        if isinstance(r["required_json"], str) and r["required_json"].strip():
            req = json.loads(r["required_json"]).get("model_name_to_qty", {})
            required = {name: int(qty)*count for name, qty in req.items()}
        if isinstance(r["optional_json"], str) and r["optional_json"].strip():
            opt = json.loads(r["optional_json"]).get("model_name_to_qty", {})
            optional = {name: int(qty)*count for name, qty in opt.items()}
    return required, optional

# Session state for "cart"
if "cart" not in st.session_state:
    st.session_state.cart = []  # list of dicts: {model_id, model_name, qty}

dfs = load_data(DATA_PATH)

# ---- Sidebar booking form ----
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

    if start_tm is None or end_tm is None or end_dt is None:
        st.info("Izberi datume in čase.")
    else:
        start = datetime.combine(start_dt, start_tm)
        end = datetime.combine(end_dt, end_tm)

        st.subheader("Dodaj opremo")
        # Choose category then model
        cat_names = dfs["categories"]["name"].tolist()
        cat_choice = st.selectbox("Kategorija", options=cat_names)
        cat_id = int(dfs["categories"].loc[dfs["categories"]["name"]==cat_choice, "id"].iloc[0])
        model_options = dfs["models"].merge(dfs["brands"], left_on="brand_id", right_on="id", suffixes=("","_b"))
        model_options = model_options[model_options["category_id"]==cat_id]
        model_options["label"] = model_options["name"] + " (" + model_options["name_b"] + ")"
        # If duplicate brand name field confusion, fix label
        model_options["label"] = model_options.apply(lambda r: f'{r["name"]} [{dfs["brands"].loc[dfs["brands"]["id"]==r["brand_id"],"name"].iloc[0]}]', axis=1)
        model_label = st.selectbox("Model", options=model_options["label"].tolist())
        # resolve model_id
        mrow = model_options.loc[model_options["label"]==model_label].iloc[0]
        model_id = int(mrow["id_x"]) if "id_x" in mrow.index else int(mrow["id"])
        qty = st.number_input("Količina", min_value=1, value=1, step=1)
        if st.button("➕ Dodaj v košarico"):
            st.session_state.cart.append({"model_id": model_id, "model_name": mrow["name"], "qty": int(qty)})

        if st.session_state.cart:
            st.write("**Košarica:**")
            st.dataframe(pd.DataFrame(st.session_state.cart))

        if st.button("🧮 Izračun ponudbe"):
            results = []
            accessories_need = {}
            for item in st.session_state.cart:
                chosen = find_items_for_model(item["model_id"], item["qty"], start, end, buf_before, buf_after, dfs)
                results.append({"model": item["model_name"], "requested": item["qty"], "assigned": len(chosen), "item_ids": chosen})
                req, opt = accessories_for_model(item["model_id"], item["qty"], dfs)
                # aggregate required accessories across all requested items
                for name, q in req.items():
                    accessories_need[name] = accessories_need.get(name, 0) + q
            st.session_state.quote = {"results": results, "accessories_need": accessories_need, "start": start, "end": end, "buf_before": buf_before, "buf_after": buf_after, "title": title}

# ---- Main area ----
st.subheader("📦 Inventar (primer)")
st.dataframe(dfs["items"].merge(dfs["models"][["id","name"]], left_on="model_id", right_on="id").drop(columns=["id"]).rename(columns={"name":"model"}))

if "quote" in st.session_state:
    st.markdown("### ✅ Rezultat – razpoložljivost")
    st.dataframe(pd.DataFrame(st.session_state["quote"]["results"]))

    # Resolve accessories availability
    need = st.session_state["quote"]["accessories_need"]
    if need:
        st.markdown("### 🔌 Predlagani dodatki (required)")
        acc_rows = []
        for model_name, qty in need.items():
            m_id = dfs["models"].loc[dfs["models"]["name"]==model_name, "id"]
            if not m_id.empty:
                m_id = int(m_id.iloc[0])
                chosen = find_items_for_model(m_id, qty, st.session_state["quote"]["start"], st.session_state["quote"]["end"],
                                              st.session_state["quote"]["buf_before"], st.session_state["quote"]["buf_after"], dfs)
                acc_rows.append({"model": model_name, "requested": qty, "assigned": len(chosen), "item_ids": chosen})
            else:
                acc_rows.append({"model": model_name, "requested": qty, "assigned": 0, "item_ids": []})
        st.dataframe(pd.DataFrame(acc_rows))
        st.caption("Če je 'assigned' < 'requested', manjka dodatkov – dodaj alternative ali zmanjša količino.")

    # Confirmation writes new event + reservations to Excel
    if st.button("💾 Potrdi in zapiši rezervacijo v Excel"):
        dfs_local = load_data(DATA_PATH)  # reload to avoid stale
        # create new event id
        new_eid = (dfs_local["events"]["id"].max() if not dfs_local["events"].empty else 0) + 1
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
        dfs_local["events"] = pd.concat([dfs_local["events"], new_event], ignore_index=True)

        # reservations from results + accessories
        to_assign = []
        for row in st.session_state["quote"]["results"]:
            for iid in row["item_ids"]:
                to_assign.append(iid)
        # accessories
        for model_name, qty in st.session_state["quote"]["accessories_need"].items():
            m_id = dfs_local["models"].loc[dfs_local["models"]["name"]==model_name, "id"]
            if not m_id.empty:
                m_id = int(m_id.iloc[0])
                for iid in find_items_for_model(m_id, qty, start, end, buf_before, buf_after, dfs_local):
                    to_assign.append(iid)

        if to_assign:
            next_id = (dfs_local["reservations"]["id"].max() if not dfs_local["reservations"].empty else 0) + 1
            rows = [{
                "id": next_id + i,
                "event_id": new_eid,
                "item_id": iid,
                "status": "CONFIRMED",
                "created_at": datetime.now()
            } for i, iid in enumerate(to_assign)]
            dfs_local["reservations"] = pd.concat([dfs_local["reservations"], pd.DataFrame(rows)], ignore_index=True)

        save_data(DATA_PATH, dfs_local)
        st.success("Rezervacija zapisana.")
        st.balloons()

st.markdown("---")
st.caption("Demo: kategorije, modeli, artikli, dogodki, rezervacije, servisni 'holds' in pravilo dodatkov (mikrofoni → XLR + stojalo).")
