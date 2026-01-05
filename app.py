import os
import sys
from flask import Flask, render_template, request, jsonify, send_from_directory
from datetime import datetime
import uuid
import json
from werkzeug.utils import secure_filename
from flask_cors import CORS
from io import BytesIO
from flask import send_file  # THÊM DÒNG NÀY

# Add modules path
sys.path.append('modules')

# Import modules
from modules.db_manager import DatabaseManager
from modules.yolo_detector import YOLODetector
from modules.fuzzy_matcher import FuzzyMatcher
from modules.ocr_engine import TextDetectionOCR

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Enable CORS (allow frontend to call API)
CORS(app)

# Create directories
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Global instances (lazy loading)
db_manager = None
yolo_detector = None
ocr_engine = None
fuzzy_matcher = None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db():
    global db_manager
    if db_manager is None:
        db_manager = DatabaseManager()
        db_manager.init_parking_slots()
    return db_manager

def get_yolo():
    global yolo_detector
    if yolo_detector is None:
        yolo_detector = YOLODetector('static/models/best.pt')
    return yolo_detector

def get_ocr():
    global ocr_engine
    if ocr_engine is None:
        ocr_engine = TextDetectionOCR()
    return ocr_engine

def get_fuzzy():
    global fuzzy_matcher
    if fuzzy_matcher is None:
        fuzzy_matcher = FuzzyMatcher('static/models/inforcar.csv')
    return fuzzy_matcher

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/process', methods=['POST'])
def process_image():
    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'No image file'}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No selected file'}), 400

        if not allowed_file(file.filename):
            return jsonify({'success': False, 'error': 'Invalid file type'}), 400
        
        # Save file safely
        safe_name = secure_filename(file.filename)
        filename = f"{uuid.uuid4().hex}_{safe_name}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        print("=" * 60)
        print("🚗 START PROCESSING VEHICLE")
        print("=" * 60)
        
        # 1. YOLO detection - Lấy brand
        yolo = get_yolo()
        yolo_result = yolo.detect(filepath)
        brand_yolo = yolo_result.get('brand', 'unknown').capitalize()
        yolo_confidence = yolo_result.get('confidence', 0)

        print(f"🎯 YOLO Detection: {brand_yolo} (confidence: {yolo_confidence:.2%})")

        # 2. OCR - Lấy list các text
        ocr = get_ocr()
        result = ocr.process_image(filepath)

        # 3. Process OCR results
        ocr_texts = []
        if result and isinstance(result, dict) and 'detections' in result:
            for detection in result['detections']:
                text = detection.get('text', '').strip()
                confidence = detection.get('confidence', 0)
                if text:
                    ocr_texts.append({'text': text, 'confidence': confidence})

        print(f"📝 OCR Raw Results: {[t['text'] for t in ocr_texts]}")

        # 4. Fuzzy match các OCR texts với database để tìm model
        fuzzy = get_fuzzy()
        selected_model = None
        # best_score = 0

        print(f"🔍 Fuzzy matching OCR texts with database (model only):")

        # Tạo list các text từ OCR (loại bỏ các text quá ngắn hoặc không có ý nghĩa)
        candidate_texts = []
        for text_item in ocr_texts:
            text = text_item['text'].upper().strip()
            confidence = text_item['confidence']
            candidate_texts.append(text)
            print(f"   Candidate: '{text}' (OCR confidence: {confidence:.2f})")

        all_matches = []
        # Fuzzy match mỗi candidate với database
        for candidate in candidate_texts:
            # Thử fuzzy match với database (chỉ model)
            match_result = fuzzy.fuzzy_match_model(candidate)
            
            if match_result:
                model_name = match_result.get('model')
                match_score = match_result.get('score', 0)
                print(f"   '{candidate}' → Matched: {model_name} (score: {match_score:.2f})")

                all_matches.append((match_score, model_name, candidate))

                # if match_score > best_score:
                #     best_score = match_score
                #     selected_model = model_name

        if all_matches:
             # Sắp xếp theo score giảm dần
            all_matches.sort(reverse=True)
            best_score, selected_model, best_candidate = all_matches[0]

            print(f"\n📊 Top matches:")
            for i, (score, model, candidate) in enumerate(all_matches[:3]):  # Top 3
                print(f"   {i+1}. '{candidate}' → {model} (score: {score:.2f})")
            
            print(f"\n🎯 Selected: '{best_candidate}' → {selected_model} (score: {best_score:.2f})")
        else:
            print("   No matches found from fuzzy matching")

        # 5. Nếu không tìm được model bằng fuzzy match, thử tìm bằng keyword matching
        if not selected_model:
            print(f"⚠️ No fuzzy match found, trying keyword matching...")
            
            # Danh sách các model phổ biến để keyword matching
            common_models = ['LANCER', 'COROLLA', 'CAMRY', 'CIVIC', 'ACCORD', 'OUTLANDER', 
                            'PAJERO', 'CX-5', 'CR-V', 'RAV4', 'RANGER', 'EVEREST', 'VF8', 'VF9']
            
            for candidate in candidate_texts:
                for model in common_models:
                    # Kiểm tra nếu model có trong candidate (case-insensitive)
                    if model.upper() in candidate.upper():
                        selected_model = model
                        print(f"   Keyword match: '{candidate}' contains '{model}'")
                        break
                if selected_model:
                    break

        # 6. Kết hợp brand từ YOLO và model từ OCR
        final_brand = brand_yolo
        final_model = selected_model

        print(f"\n🎯 FINAL RESULT:")
        print(f"   Brand (from YOLO): {final_brand}")
        print(f"   Model (from OCR fuzzy): {final_model}")

        # 7. Tìm thông tin xe đầy đủ từ database
        if final_model:
            car_info = fuzzy.find_car_info_by_brand_model(final_brand, final_model)
        else:
            # Nếu không có model, chỉ tìm bằng brand
            car_info = fuzzy.find_car_info_by_brand(final_brand)

        if not car_info:
            print("❌ No match found in database, trying fallback...")
            
            # Fallback 1: Thử tìm chỉ bằng brand
            car_info = fuzzy.find_car_info_by_brand(final_brand)
            
            # Fallback 2: Dùng thông tin mặc định
            if not car_info:
                print("⚠️ Using default car info")
                car_info = {
                    'Brand': final_brand if final_brand != 'unknown' else 'Unknown',
                    'Model': final_model or 'Unknown',
                    'Kerb Weight (kg)': '000',  # Trọng lượng trung bình
                    'Year': 'Unknown',
                    'Length (mm)': 'Unknown',
                    'Width (mm)': 'Unknown',
                    'Height (mm)': 'Unknown'
                }

        print(f"✅ Database Match Found:")
        print(f"   Brand: {car_info.get('Brand', 'Unknown')}")
        print(f"   Model: {car_info.get('Model', 'Unknown')}")
        print(f"   Weight: {car_info.get('Kerb Weight (kg)', 'Unknown')} kg")
        
        # 8. Parse trọng lượng và xác định tầng
        weight = fuzzy.parse_weight(car_info['Kerb Weight (kg)'])
        floor = 1 if weight < 1000 else 2 if weight <= 2000 else 3
        
        print(f"⚖️ Weight Analysis:")
        print(f"   Raw weight: {car_info['Kerb Weight (kg)']}")
        print(f"   Parsed weight: {car_info['Kerb Weight (kg)']}")
        print(f"   Assigned floor: {floor}")
        
        # 9. Tìm chỗ đỗ
        db = get_db()
        slot = db.find_available_slot(floor)
        if not slot:
            slot = db.find_any_available_slot()
            if slot:
                floor = slot['floor']
                print(f"   Floor fallback assigned to floor {slot['floor']}")
        
        if not slot:
            return jsonify({'success': False, 'error': 'Parking lot is full'}), 400
        
        print(f"🅿️ Assigned parking: {slot['slot_code']} (Floor {floor})")
        
        # 10. Extract license plate (if present)
        license_plate = None
        for text_item in ocr_texts:
            text = text_item['text'].upper().replace(' ', '')
            import re
            plate_pattern = r'\d{2}[A-Z]{1,2}\d{4,5}'
            match = re.search(plate_pattern, text)
            if match:
                license_plate = match.group()
                break
        
        # # 11. Lấy model_raw từ OCR (nếu có)
        # model_raw = None
        # if ocr_texts:
        #     # Lấy text có độ dài vừa phải, không quá ngắn
        #     for text_item in ocr_texts:
        #         text = text_item['text'].strip()
        #         if 3 <= len(text) <= 20:
        #             model_raw = text
        #             break
        model_raw = None
        model_corrected = selected_model  # Đã được fuzzy matching

        # Tìm OCR text tương ứng với selected_model
        if all_matches and selected_model:
            for score, matched_model, ocr_text in all_matches:
                if matched_model == selected_model:
                    model_raw = ocr_text  # Lấy OCR text gốc
                    break
            
            # Nếu không tìm thấy, lấy candidate đầu tiên
            if not model_raw and all_matches:
                model_raw = all_matches[0][2]  # candidate từ match đầu tiên

        print(f"📝 OCR → Fuzzy matching:")
        print(f"   '{model_raw}' → '{model_corrected}'")


        # 12. Save vehicle
        vehicle_data = {
            'license_plate': license_plate or f"UNK_{str(uuid.uuid4())[:6]}",
            'brand_raw': brand_yolo,
            'brand_corrected': car_info.get('Brand', 'Unknown'),
            'model_raw': model_raw or 'Unknown',
            'model_corrected': car_info.get('Model', 'Unknown'),
            'weight': weight,
            'detected_floor': floor,
            'assigned_slot': slot['slot_code'],
            'image_path': filename,
            'entry_time': datetime.now()
        }
        
        vehicle_id = db.add_vehicle(vehicle_data, slot['id'])
        
        print(f"💾 Saved to database with ID: {vehicle_id}")
        print("=" * 60)
        print("✅ PROCESSING COMPLETED SUCCESSFULLY")
        print("=" * 60)
        
        return jsonify({
            'success': True,
            'data': {
                'detection': {
                    'brand_before': brand_yolo,
                    'brand_after': car_info.get('Brand', 'Unknown'),
                    'model_before': model_raw or 'Unknown',
                    'model_after': car_info.get('Model', 'Unknown'),
                    'yolo_confidence': yolo_confidence,
                    'ocr_texts': [t['text'] for t in ocr_texts]
                },
                'vehicle': {
                    'license_plate': vehicle_data['license_plate'],
                    'weight': f"{car_info['Kerb Weight (kg)']} kg",
                    'weight_range': car_info.get('Kerb Weight (kg)', 'Unknown')
                },
                'parking': {
                    'floor': floor,
                    'slot': slot['slot_code'],
                    'slot_code': slot['slot_code']
                },
                'image_url': f'/static/uploads/{filename}',
                'entry_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        })
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/status', methods=['GET'])
def parking_status():
    try:
        db = get_db()
        status_raw = db.get_parking_status()  # whatever structure DB returns
        # Normalize status to keys 1,2,3 with expected fields
        status = {}
        for floor_idx in [1,2,3]:
            raw = status_raw.get(floor_idx) if isinstance(status_raw, dict) else None
            # support string keys
            if raw is None and isinstance(status_raw, dict):
                raw = status_raw.get(str(floor_idx))
            if raw is None:
                # fallback empty structure
                status[floor_idx] = {
                    'occupied': 0,
                    'available': 20,
                    'total': 20,
                    'occupied_slots': []
                }
            else:
                # Make sure fields exist
                status[floor_idx] = {
                    'occupied': int(raw.get('occupied', 0)),
                    'available': int(raw.get('available', max(0, raw.get('total',20)-raw.get('occupied',0)))),
                    'total': int(raw.get('total', 20)),
                    'occupied_slots': raw.get('occupied_slots', [])
                }
        return jsonify({'success': True, 'data': status})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/exit', methods=['POST'])
def vehicle_exit():
    try:
        data = request.json or {}
        license_plate = data.get('license_plate')
        if not license_plate:
            return jsonify({'success': False, 'error': 'license_plate required'}), 400
        
        db = get_db()
        success = db.vehicle_exit(license_plate)
        
        if success:
            return jsonify({'success': True, 'message': 'Vehicle exited successfully'})
        else:
            return jsonify({'success': False, 'error': 'Vehicle not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/recent', methods=['GET'])
def recent_vehicles():
    try:
        db = get_db()
        vehicles = db.get_recent_vehicles(10)
        return jsonify({'success': True, 'data': vehicles})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/static/uploads/<filename>')
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ====== CÁC ROUTES MỚI CHO QUẢN LÝ ======

@app.route('/api/clear-history', methods=['DELETE'])
def clear_history():
    """Xóa lịch sử"""
    try:
        db = get_db()
        success = db.clear_recent_history()
        
        if success:
            return jsonify({'success': True, 'message': 'History cleared successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to clear history'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/reset-system', methods=['POST'])
def reset_system():
    """Reset hệ thống"""
    try:
        db = get_db()
        success = db.reset_system()
        
        if success:
            return jsonify({'success': True, 'message': 'System reset successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to reset system'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/export-data', methods=['GET'])
def export_data():
    """Xuất dữ liệu"""
    try:
        db = get_db()
        data = db.export_all_data()
        
        # Tạo file JSON
        json_data = json.dumps(data, indent=2, default=str, ensure_ascii=False)
        bytes_io = BytesIO(json_data.encode('utf-8'))
        
        filename = f'parking_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        
        return send_file(
            bytes_io,
            mimetype='application/json',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/all-vehicles', methods=['GET'])
def get_all_vehicles():
    """Lấy tất cả xe đang đỗ"""
    try:
        db = get_db()
        vehicles = db.get_all_parked_vehicles()
        return jsonify({'success': True, 'data': vehicles})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/vehicle/<int:vehicle_id>', methods=['GET'])
def get_vehicle_details(vehicle_id):
    """Lấy chi tiết xe"""
    try:
        db = get_db()
        vehicle = db.get_vehicle_by_id(vehicle_id)
        
        if vehicle:
            return jsonify({'success': True, 'data': vehicle})
        else:
            return jsonify({'success': False, 'error': 'Vehicle not found'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/vehicle/<int:vehicle_id>', methods=['DELETE'])
def delete_vehicle(vehicle_id):
    """Xóa xe"""
    try:
        db = get_db()
        success = db.delete_vehicle(vehicle_id)
        
        if success:
            return jsonify({'success': True, 'message': 'Vehicle deleted successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to delete vehicle'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_system_stats():
    """Lấy thống kê"""
    try:
        db = get_db()
        stats = db.get_system_statistics()
        return jsonify({'success': True, 'data': stats})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    print("🚀 Starting Smart Parking System...")
    print(f"📁 Upload folder: {app.config['UPLOAD_FOLDER']}")
    print(f"📁 Database folder: database/")
    print("🌐 Server running at: http://localhost:5000")
    app.run(debug=True, port=5000, host='0.0.0.0')