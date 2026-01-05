import re
from paddleocr import PaddleOCR
import cv2
import numpy as np

class OCRProcessor:
    def __init__(self):
        """Khởi tạo PaddleOCR"""
        print("📦 Loading PaddleOCR...")
        self.ocr = PaddleOCR(
            use_angle_cls=True,
            lang='en',
            show_log=False,
            rec_model_dir=None,
            det_model_dir=None,
            cls_model_dir=None
        )
        print("✅ PaddleOCR loaded successfully")
    
    def extract_text(self, image_path):
        """Trích xuất text từ ảnh"""
        try:
            result = self.ocr.ocr(image_path, cls=True)
            detections = []
            
            if result and result[0]:
                for line in result[0]:
                    if line and len(line) >= 2:
                        text = line[1][0].strip()
                        confidence = float(line[1][1])
                        bbox = line[0]
                        
                        detections.append({
                            'text': text,
                            'confidence': confidence,
                            'bbox': bbox
                        })
            
            # Sắp xếp theo confidence giảm dần
            detections.sort(key=lambda x: x['confidence'], reverse=True)
            return detections
            
        except Exception as e:
            print(f"❌ OCR error: {e}")
            return []
    
    def extract_model(self, ocr_results):
        """Trích xuất model xe từ kết quả OCR"""
        if not ocr_results:
            return None
        
        # Các pattern cho model xe
        model_patterns = [
            r'VF\s?\d+',  # VinFast VF 8, VF9, etc.
            r'[A-Z]{1,3}\s?\d+',  # General car models
            r'Model\s?[:\-]?\s?([A-Z0-9\s]+)',
            r'Type\s?[:\-]?\s?([A-Z0-9\s]+)'
        ]
        
        for detection in ocr_results:
            text = detection['text'].upper().strip()
            
            for pattern in model_patterns:
                match = re.search(pattern, text)
                if match:
                    model = match.group(0).strip()
                    # Chuẩn hóa: VF9 -> VF 9
                    if re.match(r'^[A-Z]{2}\d+$', model):
                        model = f"{model[:2]} {model[2:]}"
                    return model
        
        # Nếu không tìm thấy pattern, trả về text có confidence cao nhất
        if ocr_results:
            return ocr_results[0]['text']
        
        return None
    
    def extract_license_plate(self, ocr_results):
        """Trích xuất biển số xe"""
        if not ocr_results:
            return None
        
        # Pattern cho biển số Việt Nam
        plate_patterns = [
            r'[0-9]{2}[A-Z]{1,2}[-\s]?[0-9]{4,5}',  # 51A-12345
            r'[0-9]{2}[A-Z]{1,2}[0-9]{4,5}',         # 51A12345
            r'[A-Z]{2}[-\s]?[0-9]{3,5}[-\s]?[A-Z]{1,2}',  # AB-123-CD
            r'\b\d{2}[A-Z]\d{4,5}\b'  # 51A12345
        ]
        
        for detection in ocr_results:
            text = detection['text'].upper().replace(' ', '')
            
            for pattern in plate_patterns:
                match = re.search(pattern, text)
                if match:
                    return match.group()
        
        return None