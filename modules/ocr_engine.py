# modules/ocr_module.py - SIÊU ĐƠN GIẢN
import sys
import importlib.util

sys.path.append('modules')

import importlib.util
spec = importlib.util.spec_from_file_location("ocrtran_module", r"modules\ocrtran.py")
ocrtran_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ocrtran_module)
# Load module của bạn

# Export thẳng class của bạn
TextDetectionOCR = ocrtran_module.TextDetectionOCR