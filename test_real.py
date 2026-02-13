import os
import time
import requests
import sys

# Configuration
API_URL = "http://127.0.0.1:8000/api"
OUTPUT_DIR = "/Users/patricksiqueira/novopojetopdfpython/e2e_outputs"
REAL_ZIP_PATH = "/Users/patricksiqueira/novopojetopdfpython/I-000017767-1_reports_deezer_1q2025.zip"

def run_test():
    print(f"🚀 Iniciando Teste com Arquivo Real: {REAL_ZIP_PATH}")
    
    if not os.path.exists(REAL_ZIP_PATH):
        print(f"❌ Arquivo não encontrado: {REAL_ZIP_PATH}")
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Upload
    print("⬆️ Enviando para /api/upload...")
    with open(REAL_ZIP_PATH, 'rb') as f:
        files = {'file': ('test_payload.zip', f, 'application/zip')}
        try:
            response = requests.post(f"{API_URL}/upload", files=files)
            response.raise_for_status()
            job_data = response.json()
            job_id = job_data['job_id']
            print(f"✅ Upload aceito! Job ID: {job_id}")
        except Exception as e:
            print(f"❌ Falha no upload: {str(e)}")
            sys.exit(1)

    # Monitor
    print("⏳ Monitorando processamento...")
    status = "processing"
    
    start_time = time.time()
    while status == "processing":
        # Increased timeout for real file processing
        if time.time() - start_time > 300: 
            print("❌ Timeout aguardando processamento (300s)")
            sys.exit(1)
            
        time.sleep(2)
        try:
            res = requests.get(f"{API_URL}/status/{job_id}")
            data = res.json()
            status = data.get('status')
            if 'progress' in data:
                 print(f"   Progress: {data['progress'].get('percentage')}% - {data.get('message', '')}")
        except Exception as e:
            print(f"⚠️ Erro no polling: {str(e)}")

    if status != "completed":
        print(f"❌ Job terminou com status: {status}")
        if 'errors' in data:
             for err in data['errors']:
                 print(f"   - {err}")
        sys.exit(1)

    print("✅ Processamento concluído com sucesso!")

    # Download
    print("⬇️ Baixando PDFs...")
    try:
        resp_zip = requests.get(f"{API_URL}/download/pdfs/{job_id}")
        if resp_zip.status_code == 200:
            zip_out_path = os.path.join(OUTPUT_DIR, "pdfs_real.zip")
            with open(zip_out_path, 'wb') as f:
                f.write(resp_zip.content)
            print(f"✅ Arquivo salvo: {zip_out_path} ({len(resp_zip.content)} bytes)")
        else:
            print(f"❌ Falha download ZIP: {resp_zip.status_code}")
    except Exception as e:
         print(f"❌ Exceção ZIP: {e}")

if __name__ == "__main__":
    run_test()
