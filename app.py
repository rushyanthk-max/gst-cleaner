import streamlit as st
import pandas as pd
import re

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

    # 3. POSITION-BASED COLUMN SCANNER
    hsn_col = None
    sku_col = None
    tax_col = None
    
    # Target exactly the specific column names e-commerce platforms use
    for col in df.columns:
        clean_col_name = str(col).strip().lower()
        if 'hsn' in clean_col_name: hsn_col = col
        if 'sku' in clean_col_name or 'fsn' in clean_col_name: sku_col = col

    # HARD TARGET SPECIFIC TAX COLUMNS FOR AMAZON AND FLIPKART
    amazon_tax_headers = ['igst rate', 'cgst rate', 'sgst rate', 'tax rate', 'invoice level tax']
    flipkart_tax_headers = ['tax percentage', 'tax rate', 'igst_rate', 'rate_percentage']
    
    # Try exact matches first
    for col in df.columns:
        c_low = str(col).strip().lower()
        if c_low in amazon_tax_headers or c_low in flipkart_tax_headers:
            tax_col = col
            break
            
    # Fallback if names are slightly shifted
    if not tax_col:
        for col in df.columns:
            c_low = str(col).strip().lower()
            if 'igst' in c_low and 'rate' in c_low:
                tax_col = col
                break
            elif 'tax' in c_low and 'rate' in c_low:
                tax_col = col
                break

    # Final emergency fallback if nothing matches
    if not tax_col:
        tax_candidates = [c for c in df.columns if 'rate' in str(c).lower() or 'tax' in str(c).lower()]
        if tax_candidates: tax_col = tax_candidates[0]

    if "Hsn/sac" in df.columns: hsn_col = "Hsn/sac"
    if "Sku" in df.columns: sku_col = "Sku"

    # 4. EXECUTE DATA RECONCILIATION
    if hsn_col:
        st.info(f"🔍 System targeted HSN Column: **'{hsn_col}'** | Tax Column: **'{tax_col}'**")
        
        # Initial Deep Clean
        df[hsn_col] = df[hsn_col].fillna("").astype(str).str.strip().str.replace(r'\.0+$', '', regex=True)
        df[hsn_col] = df[hsn_col].replace(['nan', 'None', '<na>', '<NA>'], "")
        
        if sku_col:
            df[sku_col] = df[sku_col].fillna("").astype(str).str.strip()

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

        # PASS 2: DEEP NUMERICAL TAX STANDARDIZER & VOTE CALCULATOR
        tax_corrections_made = 0
        hsn_majority_tax_map = {}

        if tax_col:
            # Clean up the raw tax text values so '18.0', '18%', and '18' match perfectly as integer numbers
            def clean_tax_string(val):
                if pd.isna(val) or str(val).strip() in ['nan', 'None', '', '<NA>']:
                    return "0"
                # Strip out percentage signs, decimals, and text characters
                s = str(val).strip().replace('%', '')
                s = re.sub(r'\.0+$', '', s) # converts 18.00 -> 18
                s = s.split('.')[0]         # fallback if it's a weird decimal string
                return s if s.isdigit() else "0"

            df['_temp_tax_clean'] = df[tax_col].apply(clean_tax_string)

            # Group by our clean HSN code and look at the standardized Tax values
            for hsn_code, group in df.groupby('_temp_hsn'):
                if hsn_code != "MISSING HSN" and not group['_temp_tax_clean'].empty:
                    # Calculate the majority dominant tax integer value
                    majority_tax = group['_temp_tax_clean'].value_counts().index[0]
                    hsn_majority_tax_map[hsn_code] = majority_tax

            # Apply the majority rule back to your original targeted tax column rows
            def harmonize_taxes(row):
                global tax_corrections_made
                hsn = row['_temp_hsn']
                current_raw_tax = str(row[tax_col]).strip()
                current_clean_tax = row['_temp_tax_clean']
                
                if hsn in hsn_majority_tax_map:
                    correct_majority_tax = hsn_majority_tax_map[hsn]
                    if current_clean_tax != correct_majority_tax:
                        tax_corrections_made += 1
                        # Maintain original formatting layout type (if the original sheet used decimals, append it back)
                        if '.' in current_raw_tax:
                            return correct_majority_tax + ".0"
                        if '%' in current_raw_tax:
                            return correct_majority_tax + "%"
                        return correct_majority_tax
                return current_raw_tax

            df[tax_col] = df.apply(harmonize_taxes, axis=1)
            df.drop(columns=['_temp_tax_clean'], inplace=True) # Trash temp column

        # PASS 3: FINALIZE EXCEL FORMULA PROTECTION SHIELD FOR HSNs
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
        df.drop(columns=['_temp_hsn'], inplace=True) # Trash the temporary column

        # 5. RENDER SUCCESS DASHBOARD
        st.success(f"✨ File parsed successfully! Cleaned up {blank_rows} blank rows.")
        st.info(f"🔢 HSN PADDING UPDATE: Processed and protected **{padded_count} HSN codes** with Excel text shields.")
        
        if tax_col and tax_corrections_made > 0:
            st.warning(f"⚖️ TAX AUTO-CORRECTION: Overwrote **{tax_corrections_made} rows** in the column **'{tax_col}'** to match the dominant majority tax rate for their HSN groups!")
        elif tax_col:
            st.success(f"✅ Tax Rate Integrity: Checked all rows under column '{tax_col}'. No conflicting tax rate instances remain.")

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
