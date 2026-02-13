import os
from dotenv import load_dotenv

load_dotenv()

# Production DB (interno ao VPS)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://sbacem_user:SbacemSecurePassword2025!@localhost:5432/sbacem_db")
UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
