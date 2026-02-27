from fastapi import APIRouter, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
import uuid
import os
import zipfile
from app.features.distribution.dist_service import DistributionService
from app.config.config import UPLOAD_DIR, OUTPUT_DIR
from jinja2 import Environment, FileSystemLoader

router = APIRouter()
template_env = Environment(loader=FileSystemLoader('app/templates'))

# Temporary in-memory job storage (should use DB in prod)
jobs = {}


def update_progress(job_id, current, total):
    if job_id in jobs:
        jobs[job_id]["progress"] = {
            "current": current,
            "total": total,
            "percentage": round((current / total) * 100, 2) if total > 0 else 0
        }


def background_process(job_id, zip_path, zip_filename=""):
    service = DistributionService()

    def progress_cb(curr, tot):
        update_progress(job_id, curr, tot)

    # Phase 1: Extract and consolidate all spreadsheets
    jobs[job_id]["message"] = "Extraindo e consolidando planilhas..."
    master_df, consolidated_file, errors = service.process_zip(
        zip_path, job_id, progress_callback=progress_cb
    )

    if master_df is None:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["errors"] = errors
        return

    # Phase 2: Group by holder and generate individual PDFs
    name_col = 'Full Name' if 'Full Name' in master_df.columns else 'Titular'
    holders = master_df.groupby(name_col)

    pdf_files = []
    pdf_dir = os.path.join(OUTPUT_DIR, f"pdfs_{job_id}")
    os.makedirs(pdf_dir, exist_ok=True)

    total_holders = len(holders)

    for i, (name, group) in enumerate(holders):
        jobs[job_id]["message"] = f"Gerando PDF {i+1} de {total_holders}: {name}..."

        # Generate charts for this holder
        chart_donut, chart_bar = service.generate_charts(group)

        # Build the flat context with all 16 variables
        context = service.build_template_context(
            holder_name=name,
            holder_df=group,
            chart_donut_b64=chart_donut,
            chart_bar_b64=chart_bar,
            zip_filename=zip_filename
        )

        # Clean name for filename
        safe_name = str(name).replace(' ', '_').replace('/', '_')
        safe_ip = str(context['ip_base']).replace('/', '_').replace(' ', '_')
        filename = f"Relatorio_{safe_name}_{safe_ip}.pdf"
        pdf_path = os.path.join(pdf_dir, filename)

        try:
            service.create_pdf(context, template_env, pdf_path)
            pdf_files.append(pdf_path)
        except Exception as e:
            errors.append(f"Error generating PDF for {name}: {str(e)}")

    # Phase 3: ZIP all PDFs together
    zip_filename_out = f"pdfs_{job_id}.zip"
    zip_path_out = os.path.join(OUTPUT_DIR, zip_filename_out)
    try:
        with zipfile.ZipFile(zip_path_out, 'w') as zip_f:
            for pdf in pdf_files:
                zip_f.write(pdf, os.path.basename(pdf))
    except Exception as e:
        errors.append(f"Error creating ZIP with PDFs: {str(e)}")

    jobs[job_id].update({
        "status": "completed",
        "consolidated": consolidated_file,
        "zip_pdfs": zip_filename_out,
        "total_holders": total_holders,
        "total_pdfs": len(pdf_files),
        "errors": errors,
        "message": f"Concluído: {len(pdf_files)} PDFs gerados com sucesso."
    })


@router.post("/upload")
async def upload_zip(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    job_id = str(uuid.uuid4())
    zip_path = os.path.join(UPLOAD_DIR, f"{job_id}_{file.filename}")

    with open(zip_path, "wb") as buffer:
        buffer.write(await file.read())

    jobs[job_id] = {
        "status": "processing",
        "progress": {"current": 0, "total": 0, "percentage": 0},
        "message": "Extraindo arquivos e processando planilhas..."
    }

    background_tasks.add_task(background_process, job_id, zip_path, file.filename)

    return {"job_id": job_id, "status": "processing"}


@router.get("/status/{job_id}")
async def get_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return JSONResponse({"status": "not_found"}, status_code=404)
    return job


@router.get("/download/consolidado/{job_id}")
async def download_consolidated(job_id: str):
    job = jobs.get(job_id)
    if job and job["status"] == "completed":
        path = os.path.join(OUTPUT_DIR, job["consolidated"])
        return FileResponse(path, filename="consolidado.xlsx")
    return JSONResponse({"error": "File not ready or not found"}, status_code=404)


@router.get("/download/pdfs/{job_id}")
async def download_pdfs(job_id: str):
    job = jobs.get(job_id)
    if job and job["status"] == "completed":
        path = os.path.join(OUTPUT_DIR, job["zip_pdfs"])
        return FileResponse(path, filename="relatorios_pdf.zip")
    return JSONResponse({"error": "File not ready or not found"}, status_code=404)
