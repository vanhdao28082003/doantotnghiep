import difflib
import csv
import re
from fuzzywuzzy import fuzz, process  # THÊM IMPORT NÀY
import pandas as pd  # THÊM IMPORT NÀY

class FuzzyMatcher:
    def __init__(self, csv_path='static/models/inforcar.csv'):
        self.csv_path = csv_path
        self.cars_data = []
        self.brands = []
        self.models = []
        self.df = None  # THÊM dataframe
        self.all_models = []  # THÊM danh sách models cho fuzzy matching
        
        self.load_database()
    
    def load_database(self):
        """Load database from CSV file"""
        print(f"📂 Loading car database from {self.csv_path}...")
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file, delimiter=';')
                
                for row in reader:
                    brand = row.get('Brand', '').strip()
                    model = row.get('Model', '').strip()
                    
                    # Save car info
                    car_info = {
                        'Brand': brand,
                        'Model': model,
                        'Year': row.get('Year', '').strip(),
                        'Length (mm)': row.get('Length (mm)', '').strip(),
                        'Width (mm)': row.get('Width (mm)', '').strip(),
                        'Height (mm)': row.get('Height (mm)', '').strip(),
                        'Kerb Weight (kg)': row.get('Kerb Weight (kg)', '').strip()
                    }
                    self.cars_data.append(car_info)
                    
                    # Add to lists for matching
                    if brand and brand.lower() not in [b.lower() for b in self.brands]:
                        self.brands.append(brand)
                    if model and model.lower() not in [m.lower() for m in self.models]:
                        self.models.append(model)
            
            print(f"✅ Loaded {len(self.cars_data)} vehicles, {len(self.brands)} brands, {len(self.models)} models")
            
            # Tạo DataFrame từ cars_data
            self.df = pd.DataFrame(self.cars_data)
            # Chuẩn hóa DataFrame
            if 'Brand' in self.df.columns:
                self.df['Brand'] = self.df['Brand'].astype(str).str.strip().str.upper()
            if 'Model' in self.df.columns:
                self.df['Model'] = self.df['Model'].astype(str).str.strip().str.upper()
            
            # Trích xuất all_models
            self._extract_all_models()
            
        except Exception as e:
            print(f"❌ Error loading CSV: {e}")
            # Tạo DataFrame rỗng nếu lỗi
            self.df = pd.DataFrame()
    
    def _extract_all_models(self):
        """Trích xuất tất cả các model từ database"""
        if not self.df.empty and 'Model' in self.df.columns:
            models = set(self.df['Model'].dropna().unique())
            self.all_models = list(models)
            print(f"📊 Extracted {len(self.all_models)} unique models for fuzzy matching")
        else:
            self.all_models = []
            print("⚠️ No models extracted from database")

    # def fuzzy_match_model(self, ocr_text, threshold=70):
    #     """
    #     Fuzzy match một OCR text với các model trong database
    #     Returns: {'model': matched_model, 'score': match_score}
    #     """
    #     if not self.all_models:
    #         print("⚠️ No models available for fuzzy matching")
    #         return None
        
    #     # Chuẩn hóa OCR text
    #     ocr_text_clean = ocr_text.upper().strip()
    #     ocr_normalized = ocr_text_clean.replace(' ', '').replace('-', '')

    #     print(f"🔍 Fuzzy matching: '{ocr_text_clean}' against {len(self.all_models)} models")
        
    #     # 1. Tìm match trực tiếp
    #     for model in self.all_models:
    #         model_normalized = model.replace(' ', '').replace('-', '')
    #         if ocr_normalized == model_normalized:
                
    #             print(f"   ✅ Exact normalized match: '{model}'")
    #             return {'model': model, 'score': 100}
        
    #     # 2. Fuzzy matching với fuzzywuzzy
    #     try:
    #         best_match, score = process.extractOne(ocr_text_clean, self.all_models, 
    #                                               scorer=fuzz.partial_ratio)
    #         print(f"   🔄 Fuzzy match result: '{best_match}' (score: {score})")
    #         if score >= threshold:
    #             return {'model': best_match, 'score': score}
    #     except Exception as e:
    #         print(f"   ⚠️ Fuzzywuzzy error: {e}")
        
    #     # 3. Kiểm tra các từ khóa model phổ biến (dùng difflib)
    #     common_model_keywords = {
    #         'LANCER': ['LANCER', 'LANCR', 'LNCER'],
    #         'COROLLA': ['COROLLA', 'COROLIA', 'COR0LLA'],
    #         'CAMRY': ['CAMRY', 'C4MRY'],
    #         'CIVIC': ['CIVIC', 'C1V1C'],
    #         'CX-5': ['CX5', 'CX-5', 'CX 5'],
    #         'CR-V': ['CRV', 'CR-V', 'CR V'],
    #         'RAV4': ['RAV4', 'RAV 4'],
    #         'RANGER': ['RANGER'],
    #         'VF8': ['VF8', 'VF 8'],
    #         'VF9': ['VF9', 'VF 9']
    #     }
        
    #     for model, keywords in common_model_keywords.items():
    #         for keyword in keywords:
    #             if keyword in ocr_text_clean:
    #                 print(f"   ✅ Keyword match: '{ocr_text_clean}' contains '{keyword}' -> {model}")
    #                 return {'model': model, 'score': 85}
        
    #     print(f"   ❌ No match found for '{ocr_text_clean}'")
    #     return None
    
    def fuzzy_match_model(self, ocr_text, threshold=0.5):  # threshold 0.8 = 80%
        """
        Fuzzy match một OCR text với các model trong database (dùng difflib)
        Returns: {'model': matched_model, 'score': match_score} hoặc None
        """
        if not self.all_models:
            return None
        
        # Chuẩn hóa OCR text
        ocr_clean = ocr_text.upper().strip()
        ocr_normalized = ocr_clean.replace(' ', '').replace('-', '')
        
        print(f"🔍 Matching: '{ocr_clean}' -> '{ocr_normalized}'")
        
        # 1. Tìm EXACT MATCH sau khi chuẩn hóa (quan trọng!)
        for model in self.all_models:
            model_normalized = model.replace(' ', '').replace('-', '')
            
            if model_normalized == ocr_normalized:
                print(f"   ✅ Exact match: '{model}'")
                return {'model': model, 'score': 100}
        
        # 2. Tìm best match với difflib
        best_match = None
        best_score = 0
        
        for model in self.all_models:
            model_normalized = model.replace(' ', '').replace('-', '')
            
            # Tính similarity
            similarity = difflib.SequenceMatcher(
                None, ocr_normalized, model_normalized
            ).ratio()
            
            if similarity > best_score:
                best_score = similarity
                best_match = model
        
        # Chuyển sang phần trăm
        score_percent = best_score * 100
        
        if best_match and best_score >= threshold:
            print(f"   🔄 Best match: '{best_match}' (score: {score_percent:.1f})")
            return {'model': best_match, 'score': score_percent}
        
        print(f"   ❌ No good match (best: {best_match}, score: {score_percent:.1f})")
        return None

    def find_car_info_by_brand_model(self, brand, model):
        """Tìm thông tin xe bằng brand và model"""
        brand_clean = str(brand).upper().strip() if brand else ""
        model_clean = str(model).upper().strip() if model else ""
        
        print(f"🔍 Searching database: Brand='{brand_clean}', Model='{model_clean}'")
        
        if self.df.empty:
            print("   ⚠️ Database is empty, using default info")
            return self.get_default_info(brand_clean, model_clean)
        
        # Tìm exact match trước
        if 'Brand' in self.df.columns and 'Model' in self.df.columns:
            exact_match = self.df[
                (self.df['Brand'].str.upper() == brand_clean) & 
                (self.df['Model'].str.upper() == model_clean)
            ]
            
            if not exact_match.empty:
                print(f"   ✅ Exact match found in database")
                return exact_match.iloc[0].to_dict()
            
            # Tìm partial match cho model
            partial_match = self.df[
                (self.df['Brand'].str.upper() == brand_clean) & 
                (self.df['Model'].str.upper().str.contains(model_clean))
            ]
            
            if not partial_match.empty:
                print(f"   ✅ Partial match found (brand exact, model contains)")
                return partial_match.iloc[0].to_dict()
            
            # Tìm bằng brand only (lấy model đầu tiên)
            brand_match = self.df[self.df['Brand'].str.upper() == brand_clean]
            if not brand_match.empty:
                print(f"   ℹ️  Brand match found, using first model")
                return brand_match.iloc[0].to_dict()
        
        print(f"   ⚠️ No match in database, using default info")
        return self.get_default_info(brand_clean, model_clean)
    
    def find_car_info_by_brand(self, brand):
        """Tìm thông tin xe chỉ bằng brand"""
        brand_clean = str(brand).upper().strip() if brand else ""
        
        if self.df.empty or 'Brand' not in self.df.columns:
            return self.get_default_info(brand_clean, "")
        
        # Lấy xe đầu tiên của brand đó
        brand_cars = self.df[self.df['Brand'].str.upper() == brand_clean]
        if not brand_cars.empty:
            return brand_cars.iloc[0].to_dict()
        
        return self.get_default_info(brand_clean, "")
    
    def get_default_info(self, brand, model):
        """Trả về thông tin mặc định khi không tìm thấy trong database"""
        default_weights = {
            'MITSUBISHI': '1300',
            'TOYOTA': '1350',
            'HONDA': '1250',
            'MAZDA': '1450',
            'FORD': '1600',
            'VINFAST': '1950',
            'HYUNDAI': '1200',
            'KIA': '1250'
        }
        
        weight = default_weights.get(brand.upper(), '1500')
        
        return {
            'Brand': brand if brand else 'Unknown',
            'Model': model if model else 'Unknown',
            'Kerb Weight (kg)': weight,
            'Year': '2023',
            'Length (mm)': '4500',
            'Width (mm)': '1800',
            'Height (mm)': '1500'
        }
    
    def normalize_text(self, text, search_list, cutoff=0.3):
        """Normalize text using fuzzy matching"""
        if not text or not search_list:
            return text or ""
        
        # Ensure text is string and lowercase
        text_str = str(text).lower().strip()
        if not text_str:
            return ""
        
        search_lower = [str(s).lower() for s in search_list]
        
        # Find closest match
        matches = difflib.get_close_matches(
            text_str, 
            search_lower, 
            n=1, 
            cutoff=cutoff
        )
        
        if matches:
            # Return original case version
            matched_lower = matches[0]
            for item in search_list:
                if str(item).lower() == matched_lower:
                    return str(item)
        
        return text_str.capitalize()
    
    def find_car_info(self, brand_input, model_input):
        """Find car information from brand and model (phương thức cũ)"""
        if not self.cars_data:
            print("❌ Car database is empty")
            return None
        
        print(f"🔍 Searching for: Brand='{brand_input}', Model='{model_input}'")
        
        # Handle None inputs
        brand_str = str(brand_input) if brand_input else ""
        model_str = str(model_input) if model_input else ""
        
        # Normalize brand
        normalized_brand = self.normalize_text(brand_str, self.brands, cutoff=0.2)
        print(f"   Brand normalized: '{brand_str}' -> '{normalized_brand}'")
        
        # Normalize model (only if model_input is not None/empty)
        normalized_model = ""
        if model_str:
            normalized_model = self.normalize_text(model_str, self.models, cutoff=0.2)
            print(f"   Model normalized: '{model_str}' -> '{normalized_model}'")
        
        # Find matching cars
        matched_cars = []
        for car in self.cars_data:
            brand_match = car['Brand'].lower() == normalized_brand.lower()
            
            # If model is provided, check model match
            if normalized_model:
                model_match = car['Model'].lower() == normalized_model.lower()
                if brand_match and model_match:
                    matched_cars.append(car)
            else:
                # If no model, just match brand
                if brand_match:
                    matched_cars.append(car)
        
        # If no exact match, try fuzzy matching
        if not matched_cars:
            print("   No exact match, trying fuzzy search...")
            for car in self.cars_data:
                brand_similar = difflib.SequenceMatcher(
                    None, 
                    car['Brand'].lower(), 
                    normalized_brand.lower()
                ).ratio()
                
                model_similar = 1.0  # Default if no model to compare
                if normalized_model:
                    model_similar = difflib.SequenceMatcher(
                        None, 
                        car['Model'].lower(), 
                        normalized_model.lower()
                    ).ratio()
                
                if brand_similar > 0.5 and model_similar > 0.4:
                    matched_cars.append(car)
        
        if matched_cars:
            print(f"   Found {len(matched_cars)} matching vehicles")
            # Return first match
            return matched_cars[0]
        
        print("   No matching vehicle found")
        
        # Return default if nothing found
        return {
            'Brand': normalized_brand or 'Unknown',
            'Model': normalized_model or 'Unknown',
            'Year': 'Unknown',
            'Length (mm)': 'Unknown',
            'Width (mm)': 'Unknown',
            'Height (mm)': 'Unknown',
            'Kerb Weight (kg)': '1500'  # Default weight
        }
    
    def parse_weight(self, weight_str):
        """Parse weight from string (handles ranges like '2600-2866')"""
        if not weight_str or weight_str == 'Unknown':
            return 1500  # Default weight
        
        try:
            # Remove non-numeric characters except dash
            weight_str = re.sub(r'[^0-9\-]', '', str(weight_str))
            
            if '-' in weight_str:
                parts = weight_str.split('-')
                if len(parts) >= 2:
                    min_w = int(parts[0])
                    max_w = int(parts[1])
                    return (min_w + max_w) // 2  # Return average
                else:
                    return int(parts[0])
            else:
                return int(weight_str)
        except:
            return 1500  # Default if parsing fails