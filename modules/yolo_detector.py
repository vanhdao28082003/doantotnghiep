import torch
from ultralytics import YOLO
import cv2

class YOLODetector:
    def __init__(self, model_path='static/models/best.pt'):
        print(f"📦 Loading YOLO model from {model_path}...")
        try:
            self.model = YOLO(model_path)
            self.model.conf = 0.3  # Lower confidence threshold
            print("✅ YOLO model loaded successfully")
        except Exception as e:
            print(f"❌ Error loading YOLO model: {e}")
            self.model = None
    
    def detect(self, image_path):
        """Detect vehicle brand from image"""
        if not self.model:
            return {'brand': 'unknown', 'confidence': 0.0}
        
        try:
            # Read image
            img = cv2.imread(image_path)
            if img is None:
                print(f"❌ Cannot read image: {image_path}")
                return {'brand': 'unknown', 'confidence': 0.0}
            
            # Run inference
            results = self.model(img, verbose=False)  # Turn off verbose
            
            # Process results
            if len(results) > 0:
                boxes = results[0].boxes
                
                if boxes is not None and len(boxes) > 0:
                    # Get detection with highest confidence
                    best_idx = torch.argmax(boxes.conf).item()
                    best_box = boxes[best_idx]
                    
                    brand_id = int(best_box.cls.item())
                    brand_name = results[0].names[brand_id]
                    confidence = best_box.conf.item()
                    
                    print(f"✅ YOLO detected: {brand_name} (confidence: {confidence:.2f})")
                    return {
                        'brand': brand_name,
                        'confidence': float(confidence),
                        'box': best_box.xyxy.tolist()[0] if hasattr(best_box.xyxy, 'tolist') else []
                    }
            
            print("⚠️ YOLO: No detection found")
            return {'brand': 'unknown', 'confidence': 0.0}
            
        except Exception as e:
            print(f"❌ YOLO detection error: {e}")
            return {'brand': 'unknown', 'confidence': 0.0}