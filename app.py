import streamlit as st
import pandas as pd
import re

# Set up clean browser tab and layout
st.set_page_config(page_title="BCPL GST Sanitizer", layout="centered")

st.title("📦 BCPL E-commerce GST Sanitizer")
st.write("Drop your raw Amazon or Flipkart sheets below to instantly wipe out errors.")

# =========================================================================
# 🛑 BCPL CONFIGURATION SETTINGS
# =========================================================================
EXACT_TAX_COLUMN_NAME = "Total Tax rate"  
EXACT_HSN_COLUMN_NAME = "Hsn/sac"         

sku_hsn_catalog = {
    "SKU_SAMPLE_1": "33049910",  
    "MUG-BLUE-01": "69111011",   
}
# =========================================================================

# 1. FILE UPLOADER COMPONENT
uploaded_file = st.file_uploader("Upload your raw Excel or CSV report", type=["xlsx", "xls", "csv"])

if uploaded_file:
    if uploaded_file.name.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(uploaded_file, dtype=str)
    else:
        df = pd.read_csv(uploaded_file, dtype=str, low_memory=False)
        
    initial_rows = len(df)
    
    # 2. REMOVE COMPLETELY BLANK ROWS
    df.dropna(how='all', inplace=True)
    blank_rows = initial_rows - len(df)

    # 3. DIRECT NAME ASSIGNMENT
    hsn_col = None
    sku_col = None
    tax_col = None
    
    for col in df.columns:
        if str(col).strip() == EXACT_HSN_COLUMN_NAME:
            hsn_col = col
        if str(col).strip() == EXACT_TAX_COLUMN_NAME:
            tax_col = col
        if str(col).strip().lower() in ['sku', 'fsn', 'seller-sku', 'item']:
            sku_col = col

    # 4. EXECUTE DATA RECONCILIATION
    if hsn_col:
        st.info(f"🎯 TARGET LOCKED -> HSN Column: **'{hsn_col}'** | Tax Column: **'{tax_col}'**")
        
        # Initial Deep Clean
        df[hsn_col] = df[hsn_col].fillna("").astype(str).str.strip().str.replace(r'\.0+$', '', regex=True)
        df[hsn_col] = df[hsn_col].replace(['nan', 'None', '<na>', '<NA>'], "")
        
        if sku_col:
            df[sku_col] = df[sku_col].fillna("").astype(str).str.strip()

        # PASS 1: Normalize HSN codes first
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

        # PASS 2: CODES TO NUMBER TRANSLATOR & VOTE ENGINE
        tax_corrections_made = 0
        hsn_majority_tax_map = {}

        if tax_col:
            # Smart translator for Amazon Product Tax Codes (PTC)
            def standard_tax_extractor(val):
                if pd.isna(val) or str(val).strip() in ['nan', 'None', '', '<NA>']:
                    return "UNKNOWN"
                s = str(val).strip().upper()
                
                # Check for common Amazon tax brackets hidden in codes
                if '18' in s or 'STANDARD' in s: return "18"
                if '5' in s or 'REDUCED' in s or 'LOW' in s: return "5"
                if '12' in s: return "12"
                if '28' in s: return "28"
                if '0' in s or 'EXEMPT' in s: return "0"
                
                return s # Fallback to original code if it's unique

            df['_temp_tax_clean'] = df[tax_col].apply(standard_tax_extractor)

            # Group by clean HSN and find the dominant tax code/value
            for hsn_code, group in df.groupby('_temp_hsn'):
                if hsn_code != "MISSING HSN" and not group['_temp_tax_clean'].empty:
                    majority_tax = group['_temp_tax_clean'].value_counts().index[0]
                    hsn_majority_tax_map[hsn_code] = majority_tax

            # Apply the majority rule back to the Product Tax Code column
            def harmonize_taxes(row):
                global tax_corrections_made
                hsn = row['_temp_hsn']
                current_raw_ptc = str(row[tax_col]).strip()
                current_clean_tax = row['_temp_tax_clean']
                
                if hsn in hsn_majority_tax_map:
                    correct_majority_value = hsn_majority_tax_map[hsn]
                    
                    # If this row is using a minority tax rate class, find a correct code from the same HSN group
                    if current_clean_tax != correct_majority_value and correct_majority_value != "UNKNOWN":
                        tax_corrections_made += 1
                        
                        # Find a sample raw Amazon code from this HSN group that matches the correct rate
                        sample_match = df[(df['_temp_hsn'] == hsn) & (df['_temp_tax_clean'] == correct_majority_value)]
                        if not sample_match.empty:
                            return str(sample_match[tax_col].iloc[0]).strip()
                        
                return current_raw_ptc

            df[tax_col] = df.apply(harmonize_taxes, axis=1)
            df.drop(columns=['_temp_tax_clean'], inplace=True)

        # PASS 3: FINALIZE PROTECTION SHIELD FOR HSNs
        padded_count = 0
        filled_count = 0
        missing_count = 0

        def wrap_hsn_shield(val):
            global padded_count, filled_count, missing_count
            if val == "MISSING HSN":
                missing_count += 1
                return "MISSING HSN"
            if val.startswith('0'):
                padded_count += 1
            return f'="{val}"'

        df[hsn_col] = df['_temp_hsn'].apply(wrap_hsn_shield)
        df.drop(columns=['_temp_hsn'], inplace=True)

        # 5. RENDER SUCCESS DASHBOARD
        st.success(f"✨ File parsed successfully! Cleaned up {blank_rows} blank rows.")
        st.info(f"🔢 HSN PADDING UPDATE: Processed and protected **{padded_count} HSN codes** with Excel text shields.")
        
        if tax_col and tax_corrections_made > 0:
            st.warning(f"⚖️ TAX AUTO-CORRECTION: Automatically aligned **{tax_corrections_made} rows** inside **'{tax_col}'** to fix conflicting tax rates based on majority rule!")
        elif tax_col:
            st.success(f"✅ Tax Rate Integrity: Checked all rows under column '{tax_col}'. No conflicting tax rate instances remain.")

        if missing_count > 0:
            st.warning(f"⚠️ Warning: Found {missing_count} fields that remain blank. Marked as 'MISSING HSN'.")
            
    else:
        st.error("❌ Column Detection Error: The script could not identify an HSN column name in your file.")

    st.write("### Data Preview Grid:")
    st.dataframe(df.head(50))
    
    csv_data = df.to_csv(index=False).encode('utf-8')
    
    # 6. DOWNLOAD COMPONENT BUTTON
    st.download_button(
        label="📥 Download Sanitized File for Repotic",
        data=csv_data,
        file_name=f"CLEANED_{uploaded_file.name.split('.')[0]}.csv",
        mime="text/csv"
    )
