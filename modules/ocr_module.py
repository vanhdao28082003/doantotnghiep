# modules/ocr_module.py - DÙNG ĐÚNG API CỦA BẠN
import sys
import os
import re

class TextDetectionOCR:
    def __init__(self):
        def __init__(self):
            print("🚀 Loading your OCR Transformer...")

            import os
            import sys
            import importlib.util

            # Thư mục chứa file ocr_aa.py
            BASE_DIR = os.path.dirname(os.path.abspath(__file__))

            # Thêm modules vào sys.path
            sys.path.append(BASE_DIR)

            # Đường dẫn tới ocrtran.py (tương đối)
            ocrtran_path = os.path.join(BASE_DIR, "ocrtran.py")

            # Import module như code cũ
            spec = importlib.util.spec_from_file_location(
                "ocrtran_module",
                ocrtran_path
            )
            ocrtran_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(ocrtran_module)

            self.detector = ocrtran_module.TextDetectionOCR()
            print("✅ Your OCR loaded")

    
    def extract_text_from_image(self, image_path):
        """Call your process_image method - ĐÚNG API CỦA BẠN"""
        result = self.detector.process_image(image_path)
        
        if not result or 'detections' not in result:
            return []
        
        # Lấy toàn bộ detections từ kết quả của bạn
        texts = []
        for det in result['detections']:
            if det.get('text'):
                texts.append({
                    'text': det['text'],
                    'confidence': det.get('confidence', 0.0),
                    'coordinates': det.get('coordinates', {})
                })
        
        print(f"📝 OCR found texts: {[t['text'] for t in texts]}")
        return texts
    
    def extract_model_from_results(self, ocr_results):
        """
        Trích xuất model từ KẾT QUẢ ĐẦY ĐỦ của bạn
        ocr_results là output của detector.process_image()
        """
        if not ocr_results or 'detections' not in ocr_results:
            return None
        
        # DỰA VÀO KẾT QUẢ THỰC TẾ CỦA BẠN:
        # ['VIN EASTS', 'VF9', 'VF9']
        
        for detection in ocr_results['detections']:
            text = detection.get('text', '').upper().strip()
            
            # Bỏ qua text không phải model
            if not text or 'VIN' in text or 'WARE' in text or len(text) < 2:
                continue
            
            # Tìm pattern model xe
            # VF9, VF 9, VE9 (OCR có thể nhầm F thành E)
            patterns = [
                r'VF\s?\d+',      # VF9, VF 9
                r'VE\s?\d+',      # VE9 (lỗi OCR)
                r'[A-Z]{2}\d+',   # XX9
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    model = match.group()
                    # Chuẩn hóa: VF9 -> VF 9
                    if ' ' not in model and len(model) > 2:
                        model = f"{model[:2]} {model[2:]}"
                    return model
        
        return None
    
    def extract_info_from_image(self, image_path):
        """
        PHƯƠNG THỨC CHÍNH - trả về tất cả thông tin cần thiết
        theo đúng format OCR của bạn
        """
        # Gọi phương thức GỐC của bạn
        result = self.detector.process_image(image_path)
        
        if not result:
            return {
                'texts': [],
                'model': None,
                'license_plate': None,
                'raw_result': None
            }
        
        # Trích xuất texts
        texts = []
        if 'detections' in result:
            for det in result['detections']:
                if det.get('text'):
                    texts.append({
                        'text': det['text'],
                        'confidence': det.get('confidence', 0.0)
                    })
        
        # Tìm model (dựa vào logic của bạn)
        model = None
        for text_item in texts:
            text = text_item['text'].upper()
            # LOGIC TÌM MODEL CỦA BẠN - điều chỉnh theo kết quả thực tế
            if 'VF' in text and any(c.isdigit() for c in text):
                # Tìm số trong text
                numbers = ''.join(filter(str.isdigit, text))
                if numbers:
                    model = f"VF {numbers}"
                    break
        
        return {
            'texts': texts,
            'model': model,
            'license_plate': None,  # Nếu cần thêm sau
            'raw_result': result  # Giữ nguyên kết quả gốc
        }