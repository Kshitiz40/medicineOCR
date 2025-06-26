from pydantic import BaseModel
from typing import Optional
from datetime import date
from enum import Enum

class ScanType(str, Enum):
    IMAGE = "image"
    BARCODE = "barcode"

class MedicineBase(BaseModel):
    medicineName: Optional[str] = None
    price: Optional[float] = None
    manufacturingDate: Optional[date] = None
    expiryDate: Optional[date] = None
    batchNumber: Optional[str] = None
    quantity: Optional[int] = None
    image_data: Optional[str] = None
    extractedText: Optional[str] = None
    scanType: ScanType

class Medicine(MedicineBase):
    id: str
    image_url: str
    created_at: str

    class Config:
        from_attributes = True