# modules/ocr_transformer.py - Tích hợp TrOCR từ file của bạn
import cv2
import numpy as np
import torch
import sys
import os

class TextDetectionOCR:
    def __init__(self, craft_path='craft_pytorch'):
        print("🚀 Initializing Transformer OCR System...")
        
        try:
            # Add craft_pytorch to path
            sys.path.insert(0, craft_path)
            
            # Import CRAFT modules
            from craft import CRAFT as CRAFTModel
            from craft_utils import getDetBoxes, adjustResultCoordinates
            from imgproc import resize_aspect_ratio, normalizeMeanVariance
            
            # Initialize CRAFT
            self.CRAFTModel = CRAFTModel
            self.getDetBoxes = getDetBoxes
            self.adjustResultCoordinates = adjustResultCoordinates
            self.resize_aspect_ratio = resize_aspect_ratio
            self.normalizeMeanVariance = normalizeMeanVariance
            
            # Load CRAFT model
            model_path = os.path.join(craft_path, 'craft_mlt_25k.pth')
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"CRAFT model not found: {model_path}")
            
            self.net = CRAFTModel()
            self.net.load_state_dict(self._copy_state_dict(torch.load(model_path, map_location='cpu')))
            self.net.eval()
            print("✅ CRAFT model loaded")
            
        except Exception as e:
            print(f"⚠️ Error loading CRAFT: {e}")
            self.net = None
        
        # Initialize Transformer OCR (TrOCR)
        try:
            from transformers import TrOCRProcessor, VisionEncoderDecoderModel
            
            print("📦 Loading Transformer OCR (TrOCR)...")
            self.processor = TrOCRProcessor.from_pretrained("microsoft/trocr-base-printed")
            self.model = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-base-printed")
            print("✅ Transformer OCR loaded successfully")
            
        except Exception as e:
            print(f"❌ Error loading Transformer OCR: {e}")
            self.processor = None
            self.model = None
    
    def _copy_state_dict(self, state_dict):
        """Copy state dict for CRAFT model"""
        if list(state_dict.keys())[0].startswith("module"):
            start_idx = 1
        else:
            start_idx = 0
        new_state_dict = {}
        for k, v in state_dict.items():
            name = ".".join(k.split(".")[start_idx:])
            new_state_dict[name] = v
        return new_state_dict
    
    def _detect_text_regions(self, image):
        """Detect text regions using CRAFT"""
        if self.net is None:
            return [], None
        
        try:
            # Preprocess image
            img_resized, target_ratio, size_heatmap = self.resize_aspect_ratio(
                image, 1280, cv2.INTER_LINEAR, 1.5
            )
            ratio_h = ratio_w = 1 / target_ratio
            
            # Normalize
            x = self.normalizeMeanVariance(img_resized)
            x = torch.from_numpy(x).permute(2, 0, 1)
            x = torch.autograd.Variable(x.unsqueeze(0))
            
            # Forward pass
            with torch.no_grad():
                y, _ = self.net(x)
            
            # Get heatmaps
            score_text = y[0,:,:,0].cpu().data.numpy()
            score_link = y[0,:,:,1].cpu().data.numpy()
            
            # Post-processing
            boxes, polys = self.getDetBoxes(score_text, score_link, 0.7, 0.4, 0.4, False)
            boxes = self.adjustResultCoordinates(boxes, ratio_w, ratio_h)
            
            return boxes, score_text
            
        except Exception as e:
            print(f"⚠️ CRAFT detection error: {e}")
            return [], None
    
    def _recognize_with_trocr(self, image_region):
        """Recognize text using TrOCR"""
        if self.processor is None or self.model is None:
            return "", 0.0
        
        try:
            from PIL import Image
            
            # Convert to PIL Image
            pil_image = Image.fromarray(image_region)
            
            # Preprocess
            pixel_values = self.processor(images=pil_image, return_tensors="pt").pixel_values
            
            # Generate text
            generated_ids = self.model.generate(pixel_values)
            text = self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            
            # TrOCR doesn't provide confidence score, so we estimate
            confidence = 0.9 if len(text.strip()) > 0 else 0.0
            
            return text.strip(), confidence
            
        except Exception as e:
            print(f"⚠️ TrOCR error: {e}")
            return "", 0.0
    
    def _enhance_image_quality(self, image):
        """Enhance image quality for OCR"""
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            
            # Enhance contrast
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            
            # Sharpen
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            sharpened = cv2.filter2D(enhanced, -1, kernel)
            
            # Convert back to RGB
            result = cv2.cvtColor(sharpened, cv2.COLOR_GRAY2RGB)
            return result
            
        except Exception as e:
            print(f"⚠️ Image enhancement error: {e}")
            return image
    
    def extract_text_from_image(self, image_path):
        """Main method: extract text from image"""
        print(f"🔍 Processing image: {image_path}")
        
        # Load image
        image = cv2.imread(image_path)
        if image is None:
            print("❌ Cannot read image")
            return []
        
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        extracted_texts = []
        
        # Detect text regions with CRAFT
        if self.net:
            print("📝 Detecting text regions with CRAFT...")
            boxes, heatmap = self._detect_text_regions(image)
            
            if boxes:
                print(f"   Found {len(boxes)} text regions")
                
                for i, box in enumerate(boxes):
                    try:
                        box = box.astype(np.int32)
                        x_min, y_min = box[:, 0].min(), box[:, 1].min()
                        x_max, y_max = box[:, 0].max(), box[:, 1].max()
                        
                        # Add margin
                        margin = 10
                        x_min = max(0, x_min - margin)
                        y_min = max(0, y_min - margin)
                        x_max = min(image.shape[1], x_max + margin)
                        y_max = min(image.shape[0], y_max + margin)
                        
                        # Crop region
                        region = image[y_min:y_max, x_min:x_max]
                        if region.size == 0:
                            continue
                        
                        # Enhance and recognize
                        enhanced = self._enhance_image_quality(region)
                        text, confidence = self._recognize_with_trocr(enhanced)
                        
                        if text:
                            print(f"   Region {i+1}: '{text}' (conf: {confidence:.2f})")
                            extracted_texts.append({
                                'text': text,
                                'confidence': confidence,
                                'bbox': box.tolist(),
                                'coordinates': {
                                    'x_min': x_min, 'y_min': y_min,
                                    'x_max': x_max, 'y_max': y_max
                                }
                            })
                            
                    except Exception as e:
                        print(f"⚠️ Error processing region {i+1}: {e}")
                        continue
            else:
                print("   No text regions found with CRAFT")
        else:
            print("⚠️ CRAFT not available, using full image OCR")
            
            # If CRAFT fails, try OCR on entire image
            enhanced = self._enhance_image_quality(image)
            text, confidence = self._recognize_with_trocr(enhanced)
            
            if text:
                extracted_texts.append({
                    'text': text,
                    'confidence': confidence,
                    'bbox': [],
                    'coordinates': {}
                })
        
        # Sort by confidence
        extracted_texts.sort(key=lambda x: x['confidence'], reverse=True)
        
        print(f"✅ OCR extracted {len(extracted_texts)} text items")
        if extracted_texts:
            print(f"   Top results: {[t['text'] for t in extracted_texts[:3]]}")
        
        return extracted_texts
    
    def extract_model_name(self, ocr_texts):
        """Extract vehicle model from OCR results"""
        if not ocr_texts:
            print("⚠️ No OCR texts to extract model from")
            return None
        
        import re
        
        # Common model patterns
        patterns = [
            r'VF\s?\d+',  # VF 8, VF9
            r'VE\s?\d+',  # VE6 (common OCR error for VF6)
            r'[A-Z]{1,3}\s?\d+[A-Z]?',  # X5, RX350
            r'MODEL\s?[:]?\s?([A-Z0-9\s]+)',
        ]
        
        for item in ocr_texts:
            text = item['text'].upper().strip()
            
            # Skip obvious non-models
            if len(text) < 2 or text in ['', 'WARE.', 'WAREHOUSE']:
                continue
            
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    model = match.group().strip()
                    
                    # Clean up
                    model = re.sub(r'MODEL\s?[:]?\s?', '', model, flags=re.IGNORECASE)
                    model = re.sub(r'TYPE\s?[:]?\s?', '', model, flags=re.IGNORECASE)
                    
                    # Standardize: VF6 -> VF 6
                    if re.match(r'^[A-Z]{2}\d+$', model):
                        model = f"{model[:2]} {model[2:]}"
                    
                    print(f"✅ Extracted model from OCR: '{model}'")
                    return model
        
        print(f"⚠️ No model pattern found in OCR texts")
        return None
    
    def extract_license_plate(self, ocr_texts):
        """Extract license plate from OCR results"""
        if not ocr_texts:
            return None
        
        import re
        
        patterns = [
            r'\b\d{2}[A-Z]{1,2}\d{4,5}\b',  # 51A12345
            r'\b\d{2}[A-Z]{1,2}[-]?\d{4,5}\b',  # 51A-12345
            r'\b[A-Z]{2}\d{3,5}[A-Z]?\b'  # AB12345
        ]
        
        for item in ocr_texts:
            text = item['text'].upper().replace(' ', '')
            
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    plate = match.group()
                    print(f"✅ Found license plate: '{plate}'")
                    return plate
        
        print("⚠️ No license plate pattern found")
        return None