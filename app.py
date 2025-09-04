import streamlit as st
from backline.db import create_db_and_tables
create_db_and_tables()

st.set_page_config(page_title="BacklinePro", page_icon="🎸", layout="wide")

# Initialize per-session state
DEFAULT_KEYS = {
    "catalog_df": None,   # DataFrame with inventory
    "cart": [],           # list of dicts: {item, model, daily_price, qty, category, brand}
    "quote_items": [],    # last saved offer items
    "current_user": "guest",  # placeholder for future auth
}
for k, v in DEFAULT_KEYS.items():
    if k not in st.session_state:
        st.session_state[k] = v

st.title("BacklinePro")
st.caption("Inventory • Booking • Offers")

c1, c2, c3 = st.columns(3)
with c1:
    if st.button("📦 Inventory"):
        # Programmatic navigation within multipage app
        st.switch_page("pages/01_Inventory.py")  # file must exist under pages/
with c2:
    if st.button("🧾 Booking"):
        st.switch_page("pages/02_Booking.py")
with c3:
    if st.button("💼 Offers"):
        st.switch_page("pages/03_Offers.py")

st.divider()
st.write("Use the left sidebar to switch pages too.")
