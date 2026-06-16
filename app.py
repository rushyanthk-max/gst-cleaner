import streamlit as st
import pandas as pd

# Set up a clean browser tab and layout
st.set_page_config(page_title="BCPL GST Sanitizer", layout="centered")

st.title("📦 BCPL E-commerce GST Sanitizer")
st.write("Drop your raw Amazon or Flipkart sheets below to instantly wipe out errors.")

# =========================================================================
# 🛑 BCPL MASTER PRODUCT CATALOG (Add your SKUs and correct HSNs here!)
# =========================================================================
sku_hsn_catalog = {
    "SKU_SAMPLE_1": "33049910",  
    "MUG-BLUE-01": "69111011",   
}
# =========================================================================

# 1. FILE UPLOADER COMPONENT
uploaded_file = st.file_uploader("Upload your raw Excel or CSV report", type=["xlsx", "xls", "csv"])

if uploaded_file:
    # Force Pandas to read every cell as raw, untouched text string
    if uploaded_file.name.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(uploaded_file, dtype=str)
    else:
        df = pd.read_csv(uploaded_file, dtype=str, low_memory=False)
        
    initial_rows = len(df)
    
    # 2. REMOVE COMPLETELY BLANK ROWS
    df.dropna(how='all', inplace=True)
    blank_rows = initial_rows - len(df)

    # 3. POSITION-BASED COLUMN SCANNER
    hsn_col = None
    sku_col = None
    
    for col in df.columns:
        clean_col_name = str(col).strip().lower()
        if 'hsn' in clean_col_name: hsn_col = col
        if 'sku' in clean_col_name or 'fsn' in clean_col_name: sku_col = col

    if "Hsn/sac" in df.columns: hsn_col = "Hsn/sac"
    if "Sku" in df.columns: sku_col = "Sku"

    # 4. EXECUTE DATA RECONCILIATION
    if hsn_col:
        # Deep clean data cells of decimal relics and system NaN flags
        df[hsn_col] = df[hsn_col].fillna("").astype(str).str.strip().str.replace(r'\.0+$', '', regex=True)
        df[hsn_col] = df[hsn_col].replace(['nan', 'None', '<na>', '<NA>'], "")
        
        if sku_col:
            df[sku_col] = df[sku_col].fillna("").astype(str).str.strip()

        filled_count = 0
        padded_count = 0
        missing_count = 0

        def auto_heal_data(row):
            global filled_count, padded_count, missing_count
            val = str(row[hsn_col]).strip()
            sku_val = str(row[sku_col]).strip() if sku_col else ""

            # Unpack Excel string formula encapsulations if they already exist
            if val.startswith('="') and val.endswith('"'):
                val = val[2:-1]

            # Fill missing cells
            if not val or val in ["", "nan", "None"]:
                if sku_val in sku_hsn_catalog:
                    filled_count += 1
                    target_hsn = sku_hsn_catalog[sku_val]
                else:
                    missing_count += 1
                    return "MISSING HSN"
            else:
                # Strip text non-digits
                target_hsn = "".join(filter(str.isdigit, val))

            # STRICT PADDING & TEXT PROTECTION
            # If it's a 7-digit code, prepend the zero string
            if len(target_hsn) == 7:
                padded_count += 1
                target_hsn = "0" + target_hsn

            # CRITICAL BIT: Wrap it in an Excel string equation text shield
            # This turns 03304991 into ="03304991", forcing Excel to treat it as absolute text
            if target_hsn and target_hsn != "MISSING HSN":
                return f'="{target_hsn}"'
                
            return target_hsn

        # Run mapping transformation logic
        df[hsn_col] = df.apply(auto_heal_data, axis=1)
        
        # 5. RENDER SUCCESS DASHBOARD
        st.success(f"✨ File parsed successfully! Cleaned up {blank_rows} blank rows.")
        st.info(f"🔢 HSN PADDING UPDATE: Processed and protected **{padded_count} HSN codes** with text shields.")
        
        if filled_count > 0:
            st.info(f"🧠 Catalog Lookup: Filled **{filled_count} empty HSN fields** using your SKU dictionary mapping.")
        if missing_count > 0:
            st.warning(f"⚠️ Warning: Found {missing_count} fields that are still blank. Marked as 'MISSING HSN'.")
            
    else:
        st.error("❌ Column Detection Error: The script could not identify an HSN column name in your file.")

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
