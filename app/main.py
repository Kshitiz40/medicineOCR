from fastapi import FastAPI, UploadFile, Form, File, HTTPException
from typing import Annotated, Optional
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from datetime import datetime
import os
import base64
from .database import db
from .models import Medicine, ScanType
from .schemas import ExtractionResponse
from .utils import encode_image, get_prompt_by_scan_type, scan_barcode, parse_ai_response, client
from tempfile import NamedTemporaryFile
import uuid
from bson import ObjectId

app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_db_client():
    db.connect()

@app.on_event("shutdown")
async def shutdown_db_client():
    db.close()

@app.post("/extract")
async def extract_info(
    scan_type: ScanType,
    file: UploadFile = File(...)
):
    """Enhanced extraction endpoint - handles both image OCR and barcode scanning"""
    # Save uploaded file temporarily
    with NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        tmp.write(await file.read())
        image_path = tmp.name

    try:
        if scan_type == "image":
            # Use AI for OCR and text extraction
            base64_image = encode_image(image_path)
            prompt = get_prompt_by_scan_type()

            stream = client.chat.completions.create(
                model="meta-llama/Llama-3.2-11B-Vision-Instruct-Turbo",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                },
                            },
                        ],
                    }
                ],
                stream=True,
            )

            output_text = ""
            for chunk in stream:
                part = chunk.choices[0].delta.content or "" if chunk.choices else ""
                output_text += part

            result_json = parse_ai_response(output_text)
            
        else:  # barcode
            # Use dedicated barcode scanning
            result_json = scan_barcode(image_path)

        # Clean up
        os.unlink(image_path)

        return JSONResponse(content=result_json, status_code=200)

    except Exception as e:
        # Clean up on error
        if os.path.exists(image_path):
            os.unlink(image_path)
        raise HTTPException(status_code=500, detail=str(e))
# @app.post("/extract")
# async def extract_info(
#     scan_type: ScanType,
#     file: UploadFile = File(...)
# ):
#     # Save uploaded file temporarily
#     with NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
#         tmp.write(await file.read())
#         image_path = tmp.name

#     base64_image = encode_image(image_path)
#     if(scan_type == 'image'):
#         prompt = """
#         You are a medicine info extractor:
#         Extract out the following in JSON format only:
#         - medicineName
#         - price
#         - manufacturingDate
#         - expiryDate
#         - batchNumber
#         - quantity
#         - extractedText
#         Do not give any false if it is not found in the given image.
#         Notes and other response also to be put in the JSON object only.
#         Return a valid JSON object that includes all these fields.
#         Only a JSON should be returned by you nothing else.
#         """

#         try:
#             # Send to Together AI
#             stream = client.chat.completions.create(
#                 model="meta-llama/Llama-3.2-11B-Vision-Instruct-Turbo",
#                 messages=[
#                     {
#                         "role": "user",
#                         "content": [
#                             {"type": "text", "text": prompt},
#                             {
#                                 "type": "image_url",
#                                 "image_url": {
#                                     "url": f"data:image/jpeg;base64,{base64_image}",
#                                 },
#                             },
#                         ],
#                     }
#                 ],
#                 stream=True,
#             )

#             output_text = ""
#             for chunk in stream:
#                 part = chunk.choices[0].delta.content or "" if chunk.choices else ""
#                 output_text += part

#             # Parse JSON response
#             result_json = parse_ai_response(output_text)

#             # Clean up
#             os.unlink(image_path)

#             return JSONResponse(content=result_json, status_code=200)

#         except Exception as e:
#             os.unlink(image_path)
#             raise HTTPException(status_code=500, detail=str(e))

#     else:
#         return JSONResponse(content={message: "Barcode image processed data"}, status_code=200)


@app.post("/save")
async def save_medicine_info(
    medicineName: Annotated[str, Form()],
    price: Annotated[str, Form()],
    batchNumber: Annotated[str, Form()],
    manufacturingDate: Annotated[str, Form()],
    quantity: Annotated[str, Form()],
    expiryDate: Annotated[str, Form()],
    scanType: Annotated[ScanType, Form()],
    extractedText: Annotated[Optional[str], Form()] = None,
    image: UploadFile = File(...)
):
    """Endpoint specifically for storing data in database"""
    try:
        image_data = await image.read()
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        record_id = str(ObjectId())
        image_url = f"/images/{record_id}.jpg"
        current_time = datetime.utcnow().isoformat()
        
        medicine_record = {
            "_id": record_id,
            "id": record_id,  # Add this for frontend compatibility
            "medicineName": medicineName,
            "price": price,
            "batchNumber": batchNumber,
            "manufacturingDate": manufacturingDate,
            "quantity": quantity,
            "expiryDate": expiryDate,
            "extractedText": extractedText,
            "scanType": scanType.value,  # Ensure it's stored as string
            "scanDateTime": current_time,  # Frontend expects this field name
            "image_url": image_url,
            "image_data": base64_image,
            "created_at": current_time  # Keep this for your backend needs
        }

        db.collection.insert_one(medicine_record)

        return JSONResponse(
            content={"status": "success", "id": record_id},
            status_code=201
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/records", response_model=List[Medicine])
async def get_all_records():
    """Get all processed medicine items"""
    try:
        items = list(db.collection.find({}))
        
        # Convert MongoDB documents to frontend-compatible format
        for item in items:
            if "_id" in item:
                item["id"] = str(item["_id"])  # Ensure id is string
                # Keep _id for MongoDB compatibility if needed
            
            # Ensure scanType is string (not enum)
            if "scanType" in item:
                item["scanType"] = str(item["scanType"])
                item["scan_type"] = str(item["scanType"])
        
        return JSONResponse(content=items, status_code=200)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/images/{image_id}")
async def get_image(image_id: str):
    try:
        record = db.collection.find_one({"_id": image_id})
        if not record or "image_data" not in record:
            raise HTTPException(status_code=404, detail="Image not found")
        
        return Response(
            content=record["image_data"],
            media_type="image/jpeg"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))