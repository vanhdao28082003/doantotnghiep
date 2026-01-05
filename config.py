# config.py
import os

# Base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Paths configuration
PATHS = {
    'craft_pytorch': os.path.join(BASE_DIR, 'craft_pytorch'),
    'craft_model': os.path.join(BASE_DIR, 'craft_pytorch', 'craft_mlt_25k.pth'),
    'yolo_model': os.path.join(BASE_DIR, 'static', 'models', 'best.pt'),
    'car_database': os.path.join(BASE_DIR, 'static', 'models', 'inforcar.csv'),
    'uploads': os.path.join(BASE_DIR, 'static', 'uploads')
}

# Create necessary directories
for path in [PATHS['craft_pytorch'], os.path.dirname(PATHS['uploads'])]:
    os.makedirs(path, exist_ok=True)

def check_system():
    """Check if all required files exist"""
    print("🔍 System Configuration Check:")
    print("=" * 50)
    
    for name, path in PATHS.items():
        if os.path.exists(path):
            print(f"   ✅ {name}: {path}")
        else:
            print(f"   ❌ {name}: {path} (NOT FOUND)")
    
    # Check if it's a file or directory
    requirements = {
        'CRAFT model file': PATHS['craft_model'],
        'YOLO model file': PATHS['yolo_model'],
        'Car database file': PATHS['car_database']
    }
    
    missing = []
    for name, path in requirements.items():
        if not os.path.isfile(path):
            missing.append(name)
    
    if missing:
        print(f"\n❌ Missing files: {', '.join(missing)}")
        return False
    
    print("\n✅ All system requirements met!")
    return True

if __name__ == '__main__':
    check_system()