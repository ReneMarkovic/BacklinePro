import streamlit as st
import pandas as pd

st.set_page_config(page_title="Booking", page_icon="🧾", layout="wide")
st.title("Booking Cart")

cart = st.session_state.get("cart", [])
if not cart:
    st.info("Your cart is empty. Add items from the Inventory page.")
    st.stop()

df = pd.DataFrame(cart)
st.dataframe(df, use_container_width=True)

with st.form("edit_cart"):
    idx_to_remove = st.multiselect("Remove rows (by index)", options=list(range(len(cart))))
    apply = st.form_submit_button("Apply")
    if apply and idx_to_remove:
        st.session_state.cart = [row for i, row in enumerate(cart) if i not in idx_to_remove]
        st.success("Removed selected items.")
        st.rerun()

st.success(f"{len(st.session_state.cart)} items in cart.")
