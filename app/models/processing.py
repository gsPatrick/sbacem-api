from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
import datetime

Base = declarative_base()

class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id = Column(String, primary_key=True)  # Simple UUID string
    status = Column(String, default="processing")  # processing, completed, failed
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    consolidated_file = Column(String, nullable=True)
    pdfs_zip_file = Column(String, nullable=True)
    error_log = Column(JSON, nullable=True)
