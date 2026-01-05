import sqlite3
from datetime import datetime
import os

class DatabaseManager:
    def __init__(self, db_path='database/parking.db'):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Khởi tạo database"""
        os.makedirs('database', exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Bảng vehicles
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vehicles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                license_plate TEXT,
                brand_raw TEXT,
                brand_corrected TEXT,
                model_raw TEXT,
                model_corrected TEXT,
                weight INTEGER,
                detected_floor INTEGER,
                assigned_slot TEXT,
                image_path TEXT,
                entry_time DATETIME,
                exit_time DATETIME,
                status TEXT DEFAULT 'parked'
            )
        ''')
        
        # Bảng parking_slots
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS parking_slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slot_code TEXT UNIQUE,
                floor INTEGER,
                is_occupied BOOLEAN DEFAULT 0,
                vehicle_id INTEGER,
                occupied_since DATETIME,
                FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def init_parking_slots(self):
        """Khởi tạo 60 chỗ đỗ (20 chỗ mỗi tầng)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Xóa slots cũ
        cursor.execute("DELETE FROM parking_slots")
        
        slots = []
        floors = ['I', 'II', 'III']
        sections = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J',
                   'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T']
        
        for floor_idx, floor_prefix in enumerate(floors, 1):
            for i, section in enumerate(sections):
                slot_code = f"{floor_prefix}.{section}"
                slots.append((slot_code, floor_idx, 0, None, None))
        
        cursor.executemany('''
            INSERT INTO parking_slots (slot_code, floor, is_occupied, vehicle_id, occupied_since)
            VALUES (?, ?, ?, ?, ?)
        ''', slots)
        
        conn.commit()
        conn.close()
        return True
    
    def find_available_slot(self, floor):
        """Tìm chỗ đỗ trống trên tầng cụ thể"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, slot_code, floor 
            FROM parking_slots 
            WHERE floor = ? AND is_occupied = 0
            LIMIT 1
        ''', (floor,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {'id': result[0], 'slot_code': result[1], 'floor': result[2]}
        return None
    
    def find_any_available_slot(self):
        """Tìm bất kỳ chỗ đỗ trống nào"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, slot_code, floor 
            FROM parking_slots 
            WHERE is_occupied = 0
            LIMIT 1
        ''')
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {'id': result[0], 'slot_code': result[1], 'floor': result[2]}
        return None
    
    def add_vehicle(self, vehicle_data, slot_id):
        """Thêm xe và cập nhật chỗ đỗ"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Thêm xe
        cursor.execute('''
            INSERT INTO vehicles (
                license_plate, brand_raw, brand_corrected, model_raw, model_corrected,
                weight, detected_floor, assigned_slot, image_path, entry_time, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            vehicle_data['license_plate'],
            vehicle_data['brand_raw'],
            vehicle_data['brand_corrected'],
            vehicle_data['model_raw'],
            vehicle_data['model_corrected'],
            vehicle_data['weight'],
            vehicle_data['detected_floor'],
            vehicle_data['assigned_slot'],
            vehicle_data['image_path'],
            vehicle_data['entry_time'],
            'parked'
        ))
        
        vehicle_id = cursor.lastrowid
        
        # Cập nhật chỗ đỗ
        cursor.execute('''
            UPDATE parking_slots 
            SET is_occupied = 1, vehicle_id = ?, occupied_since = ?
            WHERE id = ?
        ''', (vehicle_id, vehicle_data['entry_time'], slot_id))
        
        conn.commit()
        conn.close()
        return vehicle_id
    
    def get_parking_status(self):
        """Lấy trạng thái bãi đỗ"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        status = {}
        
        for floor in [1, 2, 3]:
            # Thống kê
            cursor.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN is_occupied = 1 THEN 1 ELSE 0 END) as occupied
                FROM parking_slots 
                WHERE floor = ?
            ''', (floor,))
            
            total, occupied = cursor.fetchone()
            available = total - occupied if total else 0
            
            # Danh sách xe đang đỗ
            cursor.execute('''
                SELECT 
                    ps.slot_code,
                    v.license_plate,
                    v.brand_corrected,
                    v.model_corrected,
                    v.weight,
                    v.entry_time
                FROM parking_slots ps
                LEFT JOIN vehicles v ON ps.vehicle_id = v.id
                WHERE ps.floor = ? AND ps.is_occupied = 1
                ORDER BY ps.slot_code
            ''', (floor,))
            
            occupied_slots = []
            for row in cursor.fetchall():
                occupied_slots.append({
                    'slot_code': row[0],
                    'license_plate': row[1],
                    'brand': row[2],
                    'model': row[3],
                    'weight': row[4],
                    'entry_time': row[5]
                })
            
            status[floor] = {
                'total': total or 20,
                'occupied': occupied or 0,
                'available': available or (20 - occupied) if total else 20,
                'occupied_slots': occupied_slots
            }
        
        conn.close()
        return status
    
    def vehicle_exit(self, license_plate):
        """Xe ra khỏi bãi"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tìm xe
        cursor.execute('''
            SELECT id, assigned_slot FROM vehicles 
            WHERE license_plate = ? AND status = 'parked'
        ''', (license_plate,))
        
        vehicle = cursor.fetchone()
        
        if not vehicle:
            conn.close()
            return False
        
        vehicle_id, assigned_slot = vehicle
        
        # Cập nhật trạng thái xe
        cursor.execute('''
            UPDATE vehicles 
            SET status = 'exited', exit_time = ?
            WHERE id = ?
        ''', (datetime.now(), vehicle_id))
        
        # Giải phóng chỗ đỗ
        cursor.execute('''
            UPDATE parking_slots 
            SET is_occupied = 0, vehicle_id = NULL, occupied_since = NULL
            WHERE slot_code = ?
        ''', (assigned_slot,))
        
        conn.commit()
        conn.close()
        return True
    
    def get_recent_vehicles(self, limit=10):
        """Lấy danh sách xe gần đây"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                license_plate, brand_corrected, model_corrected,
                assigned_slot, entry_time, image_path
            FROM vehicles 
            ORDER BY entry_time DESC
            LIMIT ?
        ''', (limit,))
        
        vehicles = []
        for row in cursor.fetchall():
            vehicles.append({
                'license_plate': row[0],
                'brand': row[1],
                'model': row[2],
                'slot': row[3],
                'entry_time': row[4],
                'image_path': row[5]
            })
        
        conn.close()
        return vehicles