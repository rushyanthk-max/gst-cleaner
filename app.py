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

    # 3. POSITION-BASED COLUMN SCANNER (Bypasses header text naming bugs)
    hsn_col = None
    sku_col = None
    
    # Scan columns checking for lowercase structural keyword fragments
    for col in df.columns:
        clean_col_name = str(col).strip().lower()
        if 'hsn' in clean_col_name: 
            hsn_col = col
        if 'sku' in clean_col_name or 'fsn' in clean_col_name: 
            sku_col = col

    # EMERGENCY BACKUP: If text scanning still fails, fallback to direct positions
    if not hsn_col:
        # Tries to find common e-commerce array structures by index tracking
        hsn_candidates = [c for c in df.columns if any(k in str(c).lower() for k in ['hsn', 'sac', 'code', 'commodity'])]
        if hsn_candidates:
            hsn_col = hsn_candidates[0]
            
    if not sku_col:
        sku_candidates = [c for c in df.columns if any(k in str(c).lower() for k in ['sku', 'fsn', 'seller-sku', 'item'])]
        if sku_candidates:
            sku_col = sku_candidates[0]

    # 4. EXECUTE RIGID RECONCILIATION DATA PASS
    if hsn_col:
        # Strip trailing math values (.0) and system NaNs completely out of the string data loop
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
            
            # Use fallback tracking if sku column isn't found
            sku_val = str(row[sku_col]).strip() if sku_col else ""

            # Check for structural blanks
            if not val or val in ["", "nan", "None"]:
                if sku_val in sku_hsn_catalog:
                    filled_count += 1
                    return sku_hsn_catalog[sku_val]
                else:
                    missing_count += 1
                    return "MISSING HSN"

            # FORCE ADD LEADING ZERO: Strips text fragments and matches exact numeric strings under 8 digits
            clean_digits = "".join(filter(str.isdigit, val))
            if len(clean_digits) == 7:
                padded_count += 1
                return "0" + clean_digits
                
            return clean_digits

        # Run the calculations across your dataframe frame
        df[hsn_col] = df.apply(auto_heal_data, axis=1)
        
        # 5. RENDER THE SUCCESS INTERFACE
        st.success(f"✨ File parsed successfully! Cleaned up {blank_rows} blank rows.")
        st.info(f"🔢 HSN PADDING UPDATE: Automatically fixed **{padded_count} HSN codes** by adding their missing leading zero!")
        
        if filled_count > 0:
            st.info(f"🧠 Catalog Lookup: Filled **{filled_count} empty HSN fields** using your SKU dictionary mapping.")
        if missing_count > 0:
            st.warning(f"⚠️ Warning: Found {missing_count} fields that are still blank. Marked as 'MISSING HSN'.")
            
    else:
        st.error("❌ Column Detection Error: The script could not identify an HSN column name in your file. Please verify your file's header layout.")

    # Show data table grid preview
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
