import streamlit as st
import pandas as pd
from pathlib import Path
from backline.data import (
    load_catalog_all_sheets_from_path,
    load_catalog_all_sheets_from_bytes,
)

st.set_page_config(page_title="Inventory", page_icon="📦", layout="wide")
st.title("Inventory")

# Try seed files under data/
CANDIDATES = [
    Path("data/gear_catalog.xlsx"),
    Path("data/gear_booking_sample.xlsx"),  # fallback to your original sample
]

if st.session_state.catalog_df is None:
    loaded = False
    for p in CANDIDATES:
        if p.exists():
            st.session_state.catalog_df = load_catalog_all_sheets_from_path(str(p))
            loaded = True
            st.caption(f"Loaded catalog from: `{p}`")
            break
    if not loaded:
        st.session_state.catalog_df = pd.DataFrame()

# Sidebar: upload/replace (all sheets)
with st.sidebar:
    st.subheader("Import / Replace Catalog")
    up = st.file_uploader("Excel (.xlsx) — each sheet = category", type=["xlsx"])
    if up is not None:
        st.session_state.catalog_df = load_catalog_all_sheets_from_bytes(up.read())
        st.success("Catalog loaded (merged all sheets).")
        # st.file_uploader defaults to 200 MB; can raise via config.toml. :contentReference[oaicite:5]{index=5}

df = st.session_state.catalog_df
if df is None or df.empty:
    st.info("No data yet. Upload an Excel workbook with one sheet per category.")
    st.stop()

# Filters
with st.form("filter_form"):
    c1, c2, c3 = st.columns(3)
    with c1:
        cat = st.selectbox("Category", ["(all)"] + sorted(df["category"].dropna().unique().tolist()))
    with c2:
        brand = st.selectbox("Brand", ["(all)"] + sorted(df["brand"].dropna().unique().tolist()))
    with c3:
        s = st.text_input("Search (item/model contains)")
    submitted = st.form_submit_button("Apply")

fdf = df.copy()
if cat != "(all)":
    fdf = fdf[fdf["category"] == cat]
if brand != "(all)":
    fdf = fdf[fdf["brand"] == brand]
if s:
    mask = fdf["item"].str.contains(s, case=False, na=False) | fdf["model"].str.contains(s, case=False, na=False)
    fdf = fdf[mask]

st.dataframe(fdf, use_container_width=True)

# Add to cart
st.markdown("### Add to Cart")
with st.form("add_form"):
    c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
    with c1:
        sel_idx = st.selectbox(
            "Select item",
            fdf.index.tolist(),
            format_func=lambda i: f"{fdf.loc[i, 'category']} • {fdf.loc[i, 'brand']} {fdf.loc[i, 'model']}"
        )
    with c2:
        qty = st.number_input("Qty", min_value=1, step=1, value=1)
    with c3:
        price = st.number_input("Daily price (override, optional)", min_value=0.0, value=float(fdf.loc[sel_idx, "daily_price"]))
    with c4:
        submitted2 = st.form_submit_button("Add")
    if submitted2:
        row = fdf.loc[sel_idx]
        st.session_state.cart.append({
            "item": f"{row.get('item','')}",
            "model": f"{row.get('model','')}",
            "daily_price": float(price),
            "qty": int(qty),
            "category": row.get("category", ""),
            "brand": row.get("brand", "")
        })
        st.success("Added to cart.")
