import streamlit as st
from datetime import datetime
from uuid import uuid4
import pandas as pd
from backline.pricing import price_quote
from backline.store import Quote, save_quote

st.set_page_config(page_title="Offers", page_icon="💼", layout="wide")
st.title("Create Offer")

items = st.session_state.get("cart", [])
if not items:
    st.info("Cart is empty.")
    st.stop()

with st.form("offer_form"):
    c1, c2 = st.columns(2)
    with c1:
        customer = st.text_input("Customer / Organization", value="")
        days = st.number_input("Rental days", min_value=1, value=1, step=1)
    with c2:
        note = st.text_area("Notes (optional)")
    make = st.form_submit_button("Price & Save Offer")

if make:
    priced = price_quote(items, days)
    q = Quote(
        id=str(uuid4())[:8],
        created_at=datetime.utcnow().isoformat(timespec="seconds"),
        customer=customer or "N/A",
        items=items,
        days=int(days),
        subtotal=priced["subtotal"],
        discount=priced["discount"],
        total=priced["total"],
        note=note or None
    )
    save_quote(q)
    st.success(f"Saved offer #{q.id}")
    st.session_state.quote_items = items.copy()

st.markdown("### Current Pricing")
priced = price_quote(items, int(days if 'days' in locals() else 1))
c1, c2, c3 = st.columns(3)
c1.metric("Subtotal", f"{priced['subtotal']:.2f} €")
c2.metric("Discount", f"{priced['discount']:.2f} €")
c3.metric("Total", f"{priced['total']:.2f} €")

# Export CSV for the items in the current cart
if st.button("Export offer items to CSV"):
    df = pd.DataFrame(items)
    st.download_button("Download CSV", df.to_csv(index=False).encode("utf-8"),
                       file_name="offer_items.csv", mime="text/csv")
