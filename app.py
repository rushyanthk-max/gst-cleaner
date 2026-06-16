import streamlit as st
import pandas as pd

# Set up a clean browser tab and layout
st.set_page_config(page_title="BCPL GST Sanitizer", layout="centered")

st.title("📦 BCPL E-commerce GST Sanitizer")
st.write("Drop your raw Amazon or Flipkart sheets below to instantly wipe out errors.")

# =========================================================================
# 🛑 BCPL MASTER PRODUCT CATALOG (Add your SKUs and correct HSNs here!)
# Whenever an HSN is blank, the app will use this list to automatically fill it.
# Syntax: "YOUR_SKU": "CORRECT_HSN"
# =========================================================================
sku_hsn_catalog = {
    "SKU_SAMPLE_1": "33049910",  # Example: Face cream SKU matching an 8-digit HSN
    "SKU_SAMPLE_2": "84212100",  # Example: Water filter SKU matching an 8-digit HSN
    "MUG-BLUE-01": "69111011",   # Add your real company SKUs below exactly like this
    "TSHIRT-BLK-M": "61091000",
}
# =========================================================================

# 1. FILE UPLOADER COMPONENT
uploaded_file = st.file_uploader("Upload your raw Excel or CSV report", type=["xlsx", "xls", "csv"])

if uploaded_file:
    # Read file forcing pure text interpretation
    if uploaded_file.name.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(uploaded_file, dtype=str)
    else:
        df = pd.read_csv(uploaded_file, dtype=str, low_memory=False)
        
    initial_rows = len(df)
    
    # 2. DATA CLEANING STEP 1: Remove completely blank formatting rows
    df.dropna(how='all', inplace=True)
    blank_rows = initial_rows - len(df)

    # 3. AUTO-DETECT COLUMNS FOR AMAZON OR FLIPKART
    hsn_col = None
    sku_col = None
    
    for col in df.columns:
        col_lower = str(col).lower()
        if 'hsn' in col_lower: hsn_col = col
        if 'sku' in col_lower or 'fsn' in col_lower: sku_col = col

    if "Hsn/sac" in df.columns: hsn_col = "Hsn/sac"
    if "Sku" in df.columns: sku_col = "Sku"

    # 4. EXECUTE ADVANCED DATA RECONCILIATION
    if hsn_col and sku_col:
        # Standardize strings, clean out text engine artifact expressions
        df[hsn_col] = df[hsn_col].fillna("").astype(str).str.strip().str.replace(r'\.0+$', '', regex=True)
        df[hsn_col] = df[hsn_col].replace(['nan', 'None', '<na>', '<NA>'], "")
        
        df[sku_col] = df[sku_col].fillna("").astype(str).str.strip()

        # Counter tracking for visual confirmation
        filled_count = 0
        still_missing_count = 0

        # Smart rows tracking pass loop
        def auto_heal_data(row):
            global filled_count, still_missing_count
            current_hsn = row[hsn_col]
            current_sku = row[sku_col]

            # If the HSN cell is completely empty
            if not current_hsn or current_hsn == "":
                # Check if we have this SKU registered in our catalog dictionary
                if current_sku in sku_hsn_catalog:
                    filled_count += 1
                    return sku_hsn_catalog[current_sku] # Plug in the correct HSN code!
                else:
                    still_missing_count += 1
                    return "MISSING HSN" # Fallback if SKU isn't in your catalog list yet
            
            # If HSN is present but dropped its leading zero (7 digits long)
            if len(current_hsn) == 7 and current_hsn.isdigit():
                return "0" + current_hsn
                
            return current_hsn

        # Apply the healing logic across the sheet row by row
        df[hsn_col] = df.apply(auto_heal_data, axis=1)
        
    elif sku_col:
        df[sku_col] = df[sku_col].fillna("MISSING SKU").astype(str).str.strip()

    # 5. RENDER THE INTERFACE RESULTS
    st.success(f"✨ Analysis complete! Cleaned up {blank_rows} blank formatting rows.")
    
    if 'filled_count' in locals() and filled_count > 0:
        st.info(f"🧠 Smart Catalog Match: Automatically filled **{filled_count} missing HSN codes** based on their product SKU labels!")
        
    if 'still_missing_count' in locals() and still_missing_count > 0:
        st.warning(f"⚠️ Found {still_missing_count} rows with blank HSN fields whose SKUs are not in your catalog dictionary yet. Marked as 'MISSING HSN'.")

    st.write("### Data Preview Grid:")
    st.dataframe(df.head(50))
    
    # Convert data into a download packet
    csv_data = df.to_csv(index=False).encode('utf-8')
    
    # 6. DOWNLOAD COMPONENT BUTTON
    st.download_button(
        label="📥 Download Sanitized File for Repotic",
        data=csv_data,
        file_name=f"CLEANED_{uploaded_file.name.split('.')[0]}.csv",
        mime="text/csv"
    )
