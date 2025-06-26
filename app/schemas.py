from pydantic import BaseModel
from typing import Optional

class ExtractionResponse(BaseModel):
    medicineName: Optional[str] = None
    price: Optional[float] = None
    manufacturingDate: Optional[str] = None
    expiryDate: Optional[str] = None
    batchNumber: Optional[str] = None
    quantity: Optional[int] = None
    image_data: Optional[str] = None
    extractedText: Optional[str] = None