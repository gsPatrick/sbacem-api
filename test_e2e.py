import os
import io
import time
import zipfile
import pandas as pd
import requests
import sys

# Configuration
API_URL = "http://127.0.0.1:8000/api"
OUTPUT_DIR = "/Users/patricksiqueira/novopojetopdfpython/e2e_outputs"

# Synthetic Data Generators
def create_synthetic_excel(filename, distribution_type, custom_data=None):
    """Creates a BytesIO object containing a synthetic Excel file."""
    if custom_data:
        data = custom_data
    else:
        data = {
            'Full Name': ['Silva, Alexandre', 'Oliveira, Maria', 'Silva, Alexandre', 'Santos, João', 'Oliveira, Maria'],
            'Ip Base Number': ['123.456.789', '987.654.321', '123.456.789', '456.789.123', '987.654.321'],
            'Title': ['Song A', 'Song B', 'Song C', 'Song D', 'Song E'],
            'Net amnt': [100.50, 200.75, 50.25, 300.00, 150.00],
            'Play count': [10, 20, 5, 30, 15],
            'Distribution Pool Name': ['Deezer 1Q2025', 'Deezer 1Q2025', 'Deezer 1Q2025', 'Deezer 1Q2025', 'Deezer 1Q2025'],
            'Date from': ['2025-01-01', '2025-01-01', '2025-01-01', '2025-01-01', '2025-01-01'],
            'Date to': ['2025-03-31', '2025-03-31', '2025-03-31', '2025-03-31', '2025-03-31']
        }
    df = pd.DataFrame(data)
    
    # Write to BytesIO
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    return output.read()

def create_nested_zip():
    """Creates a complex ZIP structure in memory."""
    # Inner ZIP 1 (Live Performance) - Default Data
    inner_zip1_io = io.BytesIO()
    with zipfile.ZipFile(inner_zip1_io, 'w') as z:
        z.writestr("relatorio__per_vendas.xlsx", create_synthetic_excel("relatorio__per_vendas.xlsx", "Ao vivo"))
    inner_zip1_bytes = inner_zip1_io.getvalue()

    # Inner ZIP 2 (Mechanical) - DIFFERENT DATA
    inner_zip2_io = io.BytesIO()
    data_mec = {
        'Full Name': ['Silva, Alexandre', 'Oliveira, Maria', 'Silva, Alexandre', 'Santos, João', 'Oliveira, Maria'],
        'Ip Base Number': ['123.456.789', '987.654.321', '123.456.789', '456.789.123', '987.654.321'],
        'Title': ['Música X', 'Música Y', 'Música Z', 'Música W', 'Música K'],
        'Net amnt': [50.00, 75.20, 25.10, 100.00, 60.00],
        'Play count': [5, 10, 2, 15, 8],
        'Distribution Pool Name': ['Deezer 1Q2025'] * 5,
        'Date from': ['2025-01-01'] * 5,
        'Date to': ['2025-03-31'] * 5
    }
    with zipfile.ZipFile(inner_zip2_io, 'w') as z:
        z.writestr("relatorio__mec_streaming.xlsx", create_synthetic_excel("relatorio__mec_streaming.xlsx", "Mecânica", custom_data=data_mec))
    inner_zip2_bytes = inner_zip2_io.getvalue()

    # Outer ZIP
    outer_zip_io = io.BytesIO()
    with zipfile.ZipFile(outer_zip_io, 'w') as z:
        # Folder A
        z.writestr("FolderA/inner_stats.zip", inner_zip1_bytes)
        # Folder B
        z.writestr("FolderB/inner_mech.zip", inner_zip2_bytes)
    
    outer_zip_io.seek(0)
    return outer_zip_io

def run_test():
    print(f"🚀 Iniciando Teste E2E na URL: {API_URL}")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1. Create Data
    print("📦 Gerando ZIP sintético com estrutura aninhada...")
    zip_bytes = create_nested_zip()
    
    # 2. Upload
    print("⬆️ Enviando para /api/upload...")
    files = {'file': ('test_payload.zip', zip_bytes, 'application/zip')}
    try:
        response = requests.post(f"{API_URL}/upload", files=files)
        response.raise_for_status()
        job_data = response.json()
        job_id = job_data['job_id']
        print(f"✅ Upload aceito! Job ID: {job_id}")
    except Exception as e:
        print(f"❌ Falha no upload: {str(e)}")
        sys.exit(1)

    # 3. Poll Status
    print("⏳ Monitorando processamento...")
    status = "processing"
    
    start_time = time.time()
    while status == "processing":
        if time.time() - start_time > 60:
            print("❌ Timeout aguardando processamento (60s)")
            sys.exit(1)
            
        time.sleep(1)
        try:
            res = requests.get(f"{API_URL}/status/{job_id}")
            data = res.json()
            status = data.get('status')
            
            # Print feedback
            if 'progress' in data:
                print(f"   Progress: {data['progress'].get('percentage')}% - {data.get('message', '')}")
                
        except Exception as e:
            print(f"⚠️ Erro no polling: {str(e)}")

    if status != "completed":
        print(f"❌ Job terminou com status: {status}")
        if 'errors' in data:
            print("   Erros retornados:")
            for err in data['errors']:
                print(f"   - {err}")
        sys.exit(1)

    print("✅ Processamento concluído com sucesso!")

    # 4. Download & Validate Outputs
    print("⬇️ Baixando e validando artefatos...")
    
    # Validate Consolidated Excel
    try:
        print("   Checking Consolidated Excel...")
        resp_excel = requests.get(f"{API_URL}/download/consolidated/{job_id}")
        # Note: route might be /download/consolidado/{job_id} based on reading code
        if resp_excel.status_code == 404:
             resp_excel = requests.get(f"{API_URL}/download/consolidado/{job_id}")
             
        if resp_excel.status_code == 200:
            excel_path = os.path.join(OUTPUT_DIR, "consolidado.xlsx")
            with open(excel_path, 'wb') as f:
                f.write(resp_excel.content)
            
            # Read back to verify
            df = pd.read_excel(excel_path)
            print(f"     -> OK. Lines: {len(df)}")
            if len(df) == 0:
                 print("     ❌ Falha: Excel vazio!")
        else:
            print(f"     ❌ Falha download Excel: {resp_excel.status_code}")
    except Exception as e:
        print(f"     ❌ Exceção Excel: {e}")

    # Validate PDFs ZIP
    try:
        print("   Checking PDFs ZIP...")
        resp_zip = requests.get(f"{API_URL}/download/pdfs/{job_id}")
        if resp_zip.status_code == 200:
            zip_out_path = os.path.join(OUTPUT_DIR, "pdfs.zip")
            with open(zip_out_path, 'wb') as f:
                f.write(resp_zip.content)
            
            # Open ZIP to check PDFs
            with zipfile.ZipFile(io.BytesIO(resp_zip.content)) as z:
                pdf_list = [n for n in z.namelist() if n.endswith('.pdf')]
                print(f"     -> OK. PDFs gerados: {len(pdf_list)}")
                
                if len(pdf_list) > 0:
                    # Check first PDF content
                    first_pdf = pdf_list[0]
                    with z.open(first_pdf) as pdf_file:
                        content = pdf_file.read()
                        if len(content) < 1000:
                            print(f"     ⚠️ Alerta: PDF {first_pdf} parece muito pequeno ({len(content)} bytes)")
                        else:
                            print(f"     -> Verificado: {first_pdf} tem {len(content)} bytes (parece válido)")
        else:
            print(f"     ❌ Falha download ZIP: {resp_zip.status_code}")
    except Exception as e:
         print(f"     ❌ Exceção ZIP: {e}")

    print("\n🏁 Teste E2E Finalizado.")

if __name__ == "__main__":
    run_test()
