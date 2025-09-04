from __future__ import annotations
import io
import pandas as pd
import streamlit as st

# ---- Header normalization helper ------------------------------------------------
def _normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = (
        df.columns.astype(str)
        .str.strip().str.lower()
        .str.replace(r"[^\w]+", "_", regex=True)  # spaces/punct -> underscore
        .str.strip("_")
    )
    return df

# ---- Canonicalize required columns and dtypes -----------------------------------
def _postprocess(out: pd.DataFrame) -> pd.DataFrame:
    # ensure minimal expected columns exist
    if "item" not in out.columns and "model" in out.columns:
        out["item"] = out["model"]
    for col in ["brand", "model"]:
        if col not in out.columns:
            out[col] = ""
    # map common price/qty aliases if needed
    if "daily_price" not in out.columns:
        for c in ["cena", "cena_na_dan", "price", "dailyprice", "price_day"]:
            if c in out.columns:
                out = out.rename(columns={c: "daily_price"})
                break
        if "daily_price" not in out.columns:
            out["daily_price"] = 0.0
    if "qty_available" not in out.columns:
        for c in ["qty", "quantity", "stock", "zaloga", "kolicina"]:
            if c in out.columns:
                out = out.rename(columns={c: "qty_available"})
                break
        if "qty_available" not in out.columns:
            out["qty_available"] = 0
    # enforce numeric types
    out["daily_price"] = pd.to_numeric(out["daily_price"], errors="coerce").fillna(0.0)
    out["qty_available"] = pd.to_numeric(out["qty_available"], errors="coerce").fillna(0).astype(int)
    # category should exist by this point (we add it from sheet names). Fallback:
    if "category" not in out.columns:
        out["category"] = "Uncategorized"
    return out

# ---- Load ALL sheets from a file path, add `category` = sheet name --------------
@st.cache_data(show_spinner=False)
def load_catalog_all_sheets_from_path(path: str) -> pd.DataFrame:
    """
    Reads ALL Excel sheets and concatenates them into one DataFrame.
    Adds 'category' column set to the sheet name.
    """
    sheets = pd.read_excel(path, sheet_name=None)  # dict of {sheet_name: DataFrame}
    # pandas.read_excel supports sheet_name=None for all sheets. :contentReference[oaicite:2]{index=2}
    frames = []
    for sheet_name, df in sheets.items():
        if df is None or df.empty:
            continue
        df = _normalize_cols(df)
        df = df.copy()
        df["category"] = sheet_name
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    return _postprocess(out)

# ---- Same but for uploaded bytes (st.file_uploader) -----------------------------
@st.cache_data(show_spinner=False)
def load_catalog_all_sheets_from_bytes(buf: bytes) -> pd.DataFrame:
    # For bytes, wrap in BytesIO per pandas docs. :contentReference[oaicite:3]{index=3}
    sheets = pd.read_excel(io.BytesIO(buf), sheet_name=None)
    frames = []
    for sheet_name, df in sheets.items():
        if df is None or df.empty:
            continue
        df = _normalize_cols(df)
        df = df.copy()
        df["category"] = sheet_name
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    return _postprocess(out)
