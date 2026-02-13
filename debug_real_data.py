import zipfile
import pandas as pd
import io
import os

REAL_ZIP_PATH = "/Users/patricksiqueira/novopojetopdfpython/I-000017767-1_reports_deezer_1q2025.zip"

def inspect_zip():
    print(f"📦 Inspecting: {REAL_ZIP_PATH}")
    
    if not os.path.exists(REAL_ZIP_PATH):
        print("❌ File not found!")
        return

    with zipfile.ZipFile(REAL_ZIP_PATH, 'r') as z:
        files = z.namelist()
        print(f"📂 Found {len(files)} files in ZIP.")
        
        # Find first Excel file
        excel_files = [f for f in files if f.endswith(('.xlsx', '.xls'))]
        if not excel_files:
            print("❌ No Excel files found directly in root.")
            # Check for nested zips? The service handles recursion, but let's check root first.
            nested_zips = [f for f in files if f.endswith('.zip')]
            if nested_zips:
                print(f"   Found nested ZIPs: {nested_zips}")
                # We won't recurse here, just noting it.
            return

        target_file = excel_files[0]
        print(f"📄 Reading first Excel file: {target_file}")
        
        with z.open(target_file) as f:
            try:
                # Try reading with default engine first (openpyxl)
                df = pd.read_excel(f)
            except Exception as e:
                print(f"   Error reading with openpyxl: {e}. Trying calamine...")
                f.seek(0)
                try:
                    df = pd.read_excel(f, engine='calamine')
                except Exception as e2:
                    print(f"   ❌ Failed to read Excel: {e2}")
                    return

        print("\n📊 Columns found:")
        for col in df.columns:
            print(f"   - '{col}'")
            
        print("\n👀 First 10 rows of 'Net Amount' and 'Play count':")
        possible_cols = [c for c in df.columns if 'net' in c.lower() or 'valor' in c.lower() or 'amnt' in c.lower() or 'play' in c.lower() or 'count' in c.lower()]
        if possible_cols:
            print(df[possible_cols].head(10).to_string())
            print("\ndtypes:")
            print(df[possible_cols].dtypes)
            
            # Check sums
            print("\n∑ Sums:")
            print(df[possible_cols].sum())
        else:
            print("   ⚠️ No relevant columns found.")

if __name__ == "__main__":
    inspect_zip()
