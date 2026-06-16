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
    # Force Pandas to read every cell as raw text string
    if uploaded_file.name.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(uploaded_file, dtype=str)
    else:
        df = pd.read_csv(uploaded_file, dtype=str, low_memory=False)
        
    initial_rows = len(df)
    
    # 2. REMOVE COMPLETELY BLANK ROWS
    df.dropna(how='all', inplace=True)
    blank_rows = initial_rows - len(df)

    # 3. POSITION-BASED COLUMN SCANNER (HSN, SKU, and Tax Rate)
    hsn_col = None
    sku_col = None
    tax_col = None
    
    for col in df.columns:
        clean_col_name = str(col).strip().lower()
        if 'hsn' in clean_col_name: hsn_col = col
        if 'sku' in clean_col_name or 'fsn' in clean_col_name: sku_col = col
        if 'tax' in clean_col_name or 'rate' in clean_col_name or 'igst' in clean_col_name: tax_col = col

    # Hardcoded fallback overrides for standard platforms
    if "Hsn/sac" in df.columns: hsn_col = "Hsn/sac"
    if "Sku" in df.columns: sku_col = "Sku"
    
    # Smart tax column fallbacks for Amazon MTR / Flipkart layouts
    if not tax_col:
        tax_candidates = [c for c in df.columns if any(k in str(c).lower() for k in ['igst rate', 'tax percentage', 'tax_rate', 'rate'])]
        if tax_candidates: tax_col = tax_candidates[0]

    # 4. EXECUTE DATA RECONCILIATION
    if hsn_col:
        # Initial Deep Clean
        df[hsn_col] = df[hsn_col].fillna("").astype(str).str.strip().str.replace(r'\.0+$', '', regex=True)
        df[hsn_col] = df[hsn_col].replace(['nan', 'None', '<na>', '<NA>'], "")
        
        if sku_col:
            df[sku_col] = df[sku_col].fillna("").astype(str).str.strip()
            
        if tax_col:
            # Clean up tax column strings (e.g., convert 18.0 or 18% into standard numerical text strings)
            df[tax_col] = df[tax_col].fillna("0").astype(str).str.strip().str.replace(r'\.0+$', '', regex=True).str.replace('%', '', regex=False)

        filled_count = 0
        padded_count = 0
        missing_count = 0

        # PASS 1: Normalize HSN codes first so we can accurately group them
        def initial_hsn_cleanup(row):
            val = str(row[hsn_col]).strip()
            sku_val = str(row[sku_col]).strip() if sku_col else ""

            if val.startswith('="') and val.endswith('"'):
                val = val[2:-1]

            if not val or val in ["", "nan", "None"]:
                if sku_val in sku_hsn_catalog:
                    return sku_hsn_catalog[sku_val]
                else:
                    return "MISSING HSN"
            
            clean_digits = "".join(filter(str.isdigit, val))
            if len(clean_digits) == 7:
                return "0" + clean_digits
            return clean_digits

        df['_temp_hsn'] = df.apply(initial_hsn_cleanup, axis=1)

        # PASS 2: MAJORITY TAX CALCULATION ENGINE
        tax_corrections_made = 0
        hsn_majority_tax_map = {}

        if tax_col:
            # Group by our clean HSN code and look at the Tax column values
            # .value_counts().index[0] extracts the mathematical "Mode" (the value that shows up most often)
            for hsn_code, group in df.groupby('_temp_hsn'):
                if hsn_code != "MISSING HSN" and not group[tax_col].empty:
                    majority_tax = group[tax_col].value_counts().index[0]
                    hsn_majority_tax_map[hsn_code] = majority_tax

            # Apply the majority rule back to the tax column rows
            def harmonize_taxes(row):
                global tax_corrections_made
                hsn = row['_temp_hsn']
                current_tax = row[tax_col]
                
                if hsn in hsn_majority_tax_map:
                    correct_majority_tax = hsn_majority_tax_map[hsn]
                    if current_tax != correct_majority_tax:
                        tax_corrections_made += 1
                        return correct_majority_tax
                return current_tax

            df[tax_col] = df.apply(harmonize_taxes, axis=1)

        # PASS 3: FINALIZE EXCEL FORMULA PROTECTION SHIELD FOR HSNs
        def wrap_hsn_shield(val):
            global padded_count, filled_count, missing_count
            if val == "MISSING HSN":
                missing_count += 1
                return "MISSING HSN"
            if val.startswith('0'):
                padded_count += 1
            return f'="{val}"'

        df[hsn_col] = df['_temp_hsn'].apply(wrap_hsn_shield)
        df.drop(columns=['_temp_hsn'], inplace=True) # Trash the temporary column

        # 5. RENDER SUCCESS DASHBOARD
        st.success(f"✨ File parsed successfully! Cleaned up {blank_rows} blank rows.")
        st.info(f"🔢 HSN PADDING UPDATE: Processed and protected **{padded_count} HSN codes** with Excel text shields.")
        
        if tax_col and tax_corrections_made > 0:
            st.warning(f"⚖️ TAX AUTO-CORRECTION: Identified mismatched tax rates! Automatically updated **{tax_corrections_made} rows** to match the dominant majority tax rate for their respective HSN codes.")
        elif tax_col:
            st.success("✅ Tax Rate Integrity: Checked all rows. No conflicting double tax rate instances detected across matching HSN groups.")

        if missing_count > 0:
            st.warning(f"⚠️ Warning: Found {missing_count} fields that remain blank. Marked as 'MISSING HSN'.")
            
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
