import cv2
import numpy as np
import torch
import torch.backends.cudnn as cudnn
from torch.autograd import Variable
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
from PIL import Image
import matplotlib.pyplot as plt

import sys
import os

# Thư mục chứa file ocrtran.py (modules/)
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))

# Thư mục cha: LUANVANTOTNGHIEP/
PROJECT_DIR = os.path.dirname(MODULE_DIR)

# Đường dẫn tới CRAFT-pytorch (relative, không cần ổ đĩa)
craft_path = os.path.join(PROJECT_DIR, "CRAFT-pytorch")

# Thêm vào sys.path
sys.path.insert(0, craft_path)



# CRAFT model imports và utilities
class CRAFT():
    def __init__(self):
        from craft import CRAFT as CRAFTModel
        from craft_utils import getDetBoxes, adjustResultCoordinates
        from imgproc import resize_aspect_ratio, normalizeMeanVariance
        import craft_utils
        import imgproc
        
        self.CRAFTModel = CRAFTModel
        self.getDetBoxes = getDetBoxes
        self.adjustResultCoordinates = adjustResultCoordinates
        self.resize_aspect_ratio = resize_aspect_ratio
        self.normalizeMeanVariance = normalizeMeanVariance
        self.craft_utils = craft_utils
        self.imgproc = imgproc
        
        # Load model CRAFT
        self.net = CRAFTModel()
        model_path = os.path.join(craft_path, 'craft_mlt_25k.pth')
        if not os.path.exists(model_path):
            print(f"❌ Không tìm thấy file model: {model_path}")
        # Tải model tự động hoặc hướng dẫn download
            self.download_model(model_path)
        self.net.load_state_dict(self.copyStateDict(torch.load(model_path, map_location='cpu')))
        self.net.eval()
    
    def copyStateDict(self, state_dict):
        if list(state_dict.keys())[0].startswith("module"):
            start_idx = 1
        else:
            start_idx = 0
        new_state_dict = {}
        for k, v in state_dict.items():
            name = ".".join(k.split(".")[start_idx:])
            new_state_dict[name] = v
        return new_state_dict
    
    def detect_text_regions(self, image):
        # Tiền xử lý ảnh
        img_resized, target_ratio, size_heatmap = self.resize_aspect_ratio(image, 1280, cv2.INTER_LINEAR, 1.5)
        ratio_h = ratio_w = 1 / target_ratio

        # Chuẩn hóa ảnh
        x = self.normalizeMeanVariance(img_resized)
        x = torch.from_numpy(x).permute(2, 0, 1)    # [h, w, c] to [c, h, w]
        x = Variable(x.unsqueeze(0))                # [c, h, w] to [b, c, h, w]

        # Forward pass
        with torch.no_grad():
            y, _ = self.net(x)

        # Lấy heatmaps
        score_text = y[0,:,:,0].cpu().data.numpy()
        score_link = y[0,:,:,1].cpu().data.numpy()

        # Post-processing
        boxes, polys = self.getDetBoxes(score_text, score_link, 0.7, 0.4, 0.4, False)
        boxes = self.adjustResultCoordinates(boxes, ratio_w, ratio_h)
        polys = self.adjustResultCoordinates(polys, ratio_w, ratio_h)
        
        return boxes, polys, score_text
    
class TextDetectionOCR:
    def __init__(self):
        # Khởi tạo CRAFT detector
        self.craft_detector = CRAFT()
        
       # Khởi tạo Transformer OCR (TrOCR)
        try:
            self.trocr_processor = TrOCRProcessor.from_pretrained("microsoft/trocr-base-printed")
            self.trocr_model = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-base-printed")
            print("✅ Transformer OCR (TrOCR) khởi tạo thành công")
        except Exception as e:
            print(f"⚠️ Lỗi Transformer OCR: {e}")
            self.trocr_processor = None
            self.trocr_model = None
        
        print("✅ Hệ thống khởi tạo thành công!")

    def recognize_with_trocr(self, image_region):
        """Nhận dạng text với Transformer OCR (TrOCR)"""
        if self.trocr_processor is None or self.trocr_model is None:
            return "", 0.0
        
        try:
            # Chuyển sang PIL Image
            pil_image = Image.fromarray(image_region)
            
            # Tiền xử lý
            pixel_values = self.trocr_processor(images=pil_image, return_tensors="pt").pixel_values
            
            # Nhận dạng
            generated_ids = self.trocr_model.generate(pixel_values)
            text = self.trocr_processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            
            return text, 0.9  # TrOCR không có confidence score
            
        except Exception as e:
            print(f"❌ Transformer OCR error: {e}")
            return "", 0.0

    def preprocess_image(self, image):
        """Tiền xử lý ảnh để cải thiện OCR"""
        try:
            # Chuyển sang grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            
            # Tăng độ tương phản
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            
            # Làm sắc nét
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            sharpened = cv2.filter2D(enhanced, -1, kernel)
            
            # Chuyển lại thành RGB
            result = cv2.cvtColor(sharpened, cv2.COLOR_GRAY2RGB)
            return result
            
        except Exception as e:
            print(f"Lỗi tiền xử lý ảnh: {e}")
            return image


    def load_image(self, image_path):
        """Load ảnh từ file path"""
        image = cv2.imread(image_path)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        return image
    
    def process_image(self, image_path):
        """Xử lý ảnh và trả về kết quả nhận diện"""
        # Load ảnh
        image = self.load_image(image_path)
        if image is None:
            return None
            
        original_image = image.copy()
        
        # Phát hiện vùng văn bản với CRAFT
        print("🔍 Đang phát hiện vùng văn bản với CRAFT...")
        boxes, polys, score_text = self.craft_detector.detect_text_regions(image)
        
        print(f"📊 Tìm thấy {len(boxes)} vùng văn bản")
        
        # Vẽ bounding boxes và nhận dạng văn bản
        results = []
        image_with_boxes = original_image.copy()
        
        for i, box in enumerate(boxes):
            try:
                # Chuyển đổi tọa độ box
                box = box.astype(np.int32)
                
                # Crop vùng văn bản từ ảnh gốc
                x_min, y_min = box[:, 0].min(), box[:, 1].min()
                x_max, y_max = box[:, 0].max(), box[:, 1].max()
                
                # Tính margin
                region_width = x_max - x_min
                region_height = y_max - y_min
                margin_w = max(15, region_width // 3)
                margin_h = max(15, region_height // 3)
                
                x_min = max(0, x_min - margin_w)
                y_min = max(0, y_min - margin_h)
                x_max = min(image.shape[1], x_max + margin_w)
                y_max = min(image.shape[0], y_max + margin_h)
                
                text_region = original_image[y_min:y_max, x_min:x_max]
                
                # Nhận dạng văn bản với Transformer OCR
                if text_region.size > 0:
                    print(f"  🔍 Xử lý vùng {i+1} - Kích thước: {text_region.shape}")
                    
                    # TIỀN XỬ LÝ ẢNH
                    processed_region = self.enhance_image_quality(text_region)
                    
                    # OCR với Transformer OCR
                    detected_text, confidence = self.recognize_with_trocr(processed_region)
                    
                    print(f"  ✅ Vùng {i+1}: '{detected_text}' (confidence: {confidence:.2f})")
                    
                    # Vẽ bounding box
                    cv2.polylines(image_with_boxes, [box], True, (0, 255, 0), 2)
                    
                    # Thêm text label
                    if detected_text:
                        cv2.putText(image_with_boxes, detected_text, 
                                (box[0][0], box[0][1] - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
                    
                    results.append({
                        'bbox': box.tolist(),
                        'text': detected_text,
                        'confidence': confidence,
                        'coordinates': {
                            'x_min': x_min,
                            'y_min': y_min,
                            'x_max': x_max,
                            'y_max': y_max
                        }
                    })
                    
            except Exception as e:
                print(f"❌ Lỗi xử lý vùng {i+1}: {e}")
                continue
        
        return {
            'original_image': original_image,
            'image_with_boxes': image_with_boxes,
            'heatmap': score_text,
            'detections': results
        }

    def enhance_image_quality(self, image):
        """Nâng cao chất lượng ảnh cho OCR"""
        try:
            # 1. Upscale ảnh nhỏ
            h, w = image.shape[:2]
            if h * w < 5000:  # Nếu ảnh quá nhỏ
                scale_factor = 4
            elif h * w < 10000:
                scale_factor = 3
            else:
                scale_factor = 2
                
            upscaled = cv2.resize(image, (w * scale_factor, h * scale_factor), 
                                interpolation=cv2.INTER_CUBIC)
            
            # 2. Tăng độ sáng và tương phản
            lab = cv2.cvtColor(upscaled, cv2.COLOR_RGB2LAB)
            l, a, b = cv2.split(lab)
            
            # Tăng độ sáng
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
            l_enhanced = clahe.apply(l)
            
            # Kết hợp lại
            lab_enhanced = cv2.merge([l_enhanced, a, b])
            brightened = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2RGB)
            
            # 3. Làm sắc nét
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            sharpened = cv2.filter2D(brightened, -1, kernel)
            
            # 4. Giảm nhiễu
            denoised = cv2.medianBlur(sharpened, 3)
            
            return denoised
            
        except Exception as e:
            print(f"Lỗi nâng cao chất lượng ảnh: {e}")
            return image
    
    def visualize_results(self, result, save_path=None):
        """Hiển thị kết quả"""
        fig, axes = plt.subplots(1, 2, figsize=(20, 10))
        
        # Hiển thị ảnh gốc
        axes[0].imshow(result['original_image'])
        axes[0].set_title('Ảnh gốc')
        axes[0].axis('off')
        
        # Hiển thị ảnh với bounding boxes
        axes[1].imshow(result['image_with_boxes'])
        axes[1].set_title('Vùng văn bản được phát hiện')
        axes[1].axis('off')
        
        # Hiển thị heatmap
        plt.figure(figsize=(10, 8))
        plt.imshow(result['heatmap'], cmap='hot')
        plt.title('Heatmap từ CRAFT')
        plt.colorbar()
        plt.axis('off')
        
        if save_path:
            plt.savefig(save_path, bbox_inches='tight', dpi=300)
        
        plt.tight_layout()
        plt.show()
        
        # In kết quả nhận dạng
        print("\n=== KẾT QUẢ NHẬN DẠNG VĂN BẢN ===")
        for i, detection in enumerate(result['detections']):
            print(f"Vùng {i+1}:")
            print(f"  Text: {detection['text']}")
            print(f"  Confidence: {detection['confidence']:.4f}")
            print(f"  Coordinates: {detection['coordinates']}")
            print("-" * 50)