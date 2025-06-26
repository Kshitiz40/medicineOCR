import base64
import json
import re
from tempfile import NamedTemporaryFile
from together import Together
from dotenv import load_dotenv
import os
from pyzbar import pyzbar
from PIL import Image
import cv2
import numpy as np

load_dotenv()

client = Together(api_key=os.getenv("TOGETHER_AI_API_KEY"))

def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

def get_prompt_by_scan_type() -> str:
    return """
    You are a medicine info extractor:
    Extract out the following in JSON format only:
    - medicineName
    - price
    - manufacturingDate
    - expiryDate
    - batchNumber
    - quantity
    - extractedText
    Do not give any false if it is not found in the given image.
    Notes and other response also to be put in the JSON object only.
    Return a valid JSON object that includes all these fields.
    Only a JSON should be returned by you nothing else.
    """
    # else:  # barcode
    #     return """
    #     You are a medicine info extractor from barcode:
    #     Extract out the following in JSON format only:
    #     - medicineName
    #     - price
    #     - manufacturingDate
    #     - expiryDate
    #     - batchNumber
    #     - quantity

    #     Do not include extractedText field.
    #     Do not give any false if it is not found in the given image.
    #     Return a valid JSON object that includes all these fields.
    #     Only a JSON should be returned by you nothing else.
    #     """

def parse_ai_response(output_text: str) -> dict:
    try:
        result_json = json.loads(output_text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', output_text, re.DOTALL)
        if match:
            json_text = match.group(0)
            result_json = json.loads(json_text)
        else:
            raise ValueError("Failed to parse JSON response from AI")
    return result_json

def enhance_image_for_barcode(image_path: str) -> str:
    """Enhance image for better barcode detection"""
    # Read image
    img = cv2.imread(image_path)
    
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Apply adaptive thresholding
    thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    
    # Save enhanced image
    enhanced_path = image_path.replace('.jpg', '_enhanced.jpg')
    cv2.imwrite(enhanced_path, thresh)
    
    return enhanced_path

def scan_barcode(image_path: str) -> dict:
    """Scan barcode from image and return extracted data"""
    try:
        # Try with original image first
        image = Image.open(image_path)
        barcodes = pyzbar.decode(image)
        
        # If no barcodes found, try with enhanced image
        if not barcodes:
            enhanced_path = enhance_image_for_barcode(image_path)
            enhanced_image = Image.open(enhanced_path)
            barcodes = pyzbar.decode(enhanced_image)
            # Clean up enhanced image
            if os.path.exists(enhanced_path):
                os.unlink(enhanced_path)
        
        if not barcodes:
            raise ValueError("No barcode detected in the image")
        
        # Process the first barcode found
        barcode = barcodes[0]
        barcode_data = barcode.data.decode('utf-8')
        barcode_type = barcode.type
        
        # Try to get medicine info from barcode data
        medicine_info = get_medicine_info_from_barcode(barcode_data, barcode_type)
        
        return {
            "medicineName": medicine_info.get("medicineName", ""),
            "price": medicine_info.get("price", ""),
            "manufacturingDate": medicine_info.get("manufacturingDate", ""),
            "expiryDate": medicine_info.get("expiryDate", ""),
            "batchNumber": medicine_info.get("batchNumber", ""),
            "quantity": medicine_info.get("quantity", ""),
            "barcodeData": barcode_data,
            "barcodeType": barcode_type
        }
        
    except Exception as e:
        raise ValueError(f"Barcode scanning failed: {str(e)}")

def get_medicine_info_from_barcode(barcode_data: str, barcode_type: str) -> dict:
    """
    Get medicine information from barcode data.
    This function can be enhanced to use various APIs or databases.
    """
    medicine_info = {
        "medicineName": "",
        "price": "",
        "manufacturingDate": "",
        "expiryDate": "",
        "batchNumber": "",
        "quantity": ""
    }
    
    # Try different approaches based on barcode type
    if barcode_type in ['EAN13', 'EAN8', 'UPCA', 'UPCE']:
        # Try to get product info from UPC/EAN databases
        medicine_info = get_product_info_from_upc_database(barcode_data)
    elif barcode_type == 'CODE128':
        # CODE128 might contain encoded medicine information
        medicine_info = parse_code128_medicine_data(barcode_data)
    elif barcode_type == 'DATAMATRIX':
        # DataMatrix often contains detailed medicine information
        medicine_info = parse_datamatrix_medicine_data(barcode_data)
    
    return medicine_info

def get_product_info_from_upc_database(barcode_data: str) -> dict:
    """
    Get product information from UPC database APIs.
    You can use APIs like:
    - OpenFoodFacts API
    - UPC Database API
    - Barcode Spider API
    """
    medicine_info = {
        "medicineName": "",
        "price": "",
        "manufacturingDate": "",
        "expiryDate": "",
        "batchNumber": "",
        "quantity": ""
    }
    
    try:
        # Example using UPC Database API (you'll need to sign up for an API key)
        api_key = os.getenv("UPC_DATABASE_API_KEY")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json"
        }
        url = f"https://api.upcitemdb.com/prod/trial/lookup?upc={barcode_data}"
        response = requests.get(url, headers=headers, timeout=10)
        
        # For now, we'll use a mock implementation
        # In production, implement actual API calls
        
        # You can also try OpenFoodFacts for some products
        # url = f"https://world.openfoodfacts.org/api/v0/product/{barcode_data}.json"
        # response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 1:
                product = data.get('product', {})
                medicine_info["medicineName"] = product.get('product_name', '')
                # OpenFoodFacts doesn't typically have medicine data, but it's an example
        
    except Exception as e:
        print(f"Error fetching from UPC database: {e}")
    
    return medicine_info

def parse_code128_medicine_data(barcode_data: str) -> dict:
    """
    Parse CODE128 barcode data for medicine information.
    This is often used for custom encoding of medicine data.
    """
    medicine_info = {
        "medicineName": "",
        "price": "",
        "manufacturingDate": "",
        "expiryDate": "",
        "batchNumber": "",
        "quantity": ""
    }
    
    # Example parsing logic - adjust based on your barcode format
    # Many medicine barcodes follow GS1 standards
    if barcode_data.startswith('01'):  # GTIN
        # Parse GS1 format
        medicine_info = parse_gs1_barcode(barcode_data)
    
    return medicine_info

def parse_datamatrix_medicine_data(barcode_data: str) -> dict:
    """
    Parse DataMatrix barcode data for medicine information.
    DataMatrix is commonly used for pharmaceuticals and can contain rich data.
    """
    medicine_info = {
        "medicineName": "",
        "price": "",
        "manufacturingDate": "",
        "expiryDate": "",
        "batchNumber": "",
        "quantity": ""
    }
    
    # DataMatrix often contains structured data
    # Example format: "01{GTIN}17{EXPIRY}10{BATCH}21{SERIAL}"
    if barcode_data.startswith('01'):
        medicine_info = parse_gs1_barcode(barcode_data)
    
    return medicine_info

def parse_gs1_barcode(barcode_data: str) -> dict:
    """
    Parse GS1 standard barcode data.
    GS1 Application Identifiers (AI) are used in pharmaceutical barcoding.
    """
    medicine_info = {
        "medicineName": "",
        "price": "",
        "manufacturingDate": "",
        "expiryDate": "",
        "batchNumber": "",
        "quantity": ""
    }
    
    # GS1 Application Identifiers
    gs1_patterns = {
        r'01(\d{14})': 'gtin',           # GTIN
        r'17(\d{6})': 'expiry',          # Expiry date (YYMMDD)
        r'10([^\\x1D]+)': 'batch',       # Batch/Lot number
        r'21([^\\x1D]+)': 'serial',      # Serial number
        r'30(\d+)': 'quantity'           # Quantity
    }
    
    for pattern, field in gs1_patterns.items():
        match = re.search(pattern, barcode_data)
        if match:
            value = match.group(1)
            if field == 'expiry':
                # Convert YYMMDD to readable format
                if len(value) == 6:
                    year = f"20{value[:2]}"
                    month = value[2:4]
                    day = value[4:6]
                    medicine_info["expiryDate"] = f"{year}-{month}-{day}"
            elif field == 'batch':
                medicine_info["batchNumber"] = value
            elif field == 'quantity':
                medicine_info["quantity"] = value
            elif field == 'gtin':
                # You could use GTIN to lookup product name from a database
                pass
    
    return medicine_info