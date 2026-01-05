import sqlite3
from datetime import datetime
import json
from pathlib import Path

class DatabaseManager:
    def __init__(self, db_path='database/parking.db'):
        # Đảm bảo thư mục database tồn tại
        Path('database').mkdir(exist_ok=True)
        self.db_path = db_path
        self.init_db()
        self.init_parking_slots()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Vehicles table
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
        
        # Parking slots table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS parking_slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slot_code TEXT UNIQUE,
                floor INTEGER,
                is_occupied BOOLEAN DEFAULT 0,
                vehicle_id INTEGER,
                FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def init_parking_slots(self):
        """Khởi tạo hoặc reset các slot đỗ xe"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Clear existing slots
        cursor.execute("DELETE FROM parking_slots")
        
        # Create 60 slots (20 per floor)
        slots = []
        for floor in [1, 2, 3]:
            floor_prefix = ['I', 'II', 'III'][floor-1]
            for i in range(20):
                slot_code = f"{floor_prefix}.{chr(65 + i)}"
                slots.append((slot_code, floor, 0, None))
        
        cursor.executemany(
            "INSERT INTO parking_slots (slot_code, floor, is_occupied, vehicle_id) VALUES (?, ?, ?, ?)",
            slots
        )
        
        conn.commit()
        conn.close()
        return True
    
    def find_available_slot(self, floor):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Để trả về dictionary
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, slot_code, floor 
            FROM parking_slots 
            WHERE floor = ? AND is_occupied = 0
            LIMIT 1
        ''', (floor,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def find_any_available_slot(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, slot_code, floor 
            FROM parking_slots 
            WHERE is_occupied = 0
            LIMIT 1
        ''')
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def add_vehicle(self, vehicle_data, slot_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Add vehicle
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
        
        # Update slot
        cursor.execute('''
            UPDATE parking_slots 
            SET is_occupied = 1, vehicle_id = ?
            WHERE id = ?
        ''', (vehicle_id, slot_id))
        
        conn.commit()
        conn.close()
        return vehicle_id
    
    def get_parking_status(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        status = {}
        
        for floor in [1, 2, 3]:
            # Get counts
            cursor.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN is_occupied = 1 THEN 1 ELSE 0 END) as occupied
                FROM parking_slots 
                WHERE floor = ?
            ''', (floor,))
            
            row = cursor.fetchone()
            total = row['total'] if row else 0
            occupied = row['occupied'] if row and row['occupied'] else 0
            available = total - occupied
            
            # Get occupied slots details
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
            ''', (floor,))
            
            occupied_slots = []
            for row in cursor.fetchall():
                occupied_slots.append(dict(row))
            
            status[floor] = {
                'total': total or 20,
                'occupied': occupied,
                'available': available,
                'occupied_slots': occupied_slots
            }
        
        conn.close()
        return status
    
    def vehicle_exit(self, license_plate):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Find vehicle
        cursor.execute('''
            SELECT id, assigned_slot FROM vehicles 
            WHERE license_plate = ? AND status = 'parked'
        ''', (license_plate,))
        
        vehicle = cursor.fetchone()
        if not vehicle:
            conn.close()
            return False
        
        vehicle_id, slot_code = vehicle
        
        # Update vehicle status
        cursor.execute('''
            UPDATE vehicles 
            SET status = 'exited', exit_time = ?
            WHERE id = ?
        ''', (datetime.now(), vehicle_id))
        
        # Free parking slot
        cursor.execute('''
            UPDATE parking_slots 
            SET is_occupied = 0, vehicle_id = NULL
            WHERE slot_code = ?
        ''', (slot_code,))
        
        conn.commit()
        conn.close()
        return True
    
    def get_recent_vehicles(self, limit=10):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                id,
                license_plate, 
                brand_corrected, 
                model_corrected,
                assigned_slot, 
                entry_time, 
                image_path,
                weight,
                detected_floor as floor
            FROM vehicles 
            ORDER BY entry_time DESC
            LIMIT ?
        ''', (limit,))
        
        vehicles = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return vehicles
    
    # ====== CÁC PHƯƠNG THỨC MỚI ======
    
    def clear_recent_history(self):
        """Xóa tất cả lịch sử xe"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM vehicles")
            cursor.execute("UPDATE parking_slots SET is_occupied = 0, vehicle_id = NULL")
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"Error clearing history: {e}")
            return False
    
    def reset_system(self):
        """Reset toàn bộ hệ thống"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Xóa tất cả xe
            cursor.execute("DELETE FROM vehicles")
            # Reset tất cả slot về trạng thái trống
            cursor.execute("UPDATE parking_slots SET is_occupied = 0, vehicle_id = NULL")
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"Error resetting system: {e}")
            return False
    
    def export_all_data(self):
        """Xuất toàn bộ dữ liệu"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Lấy tất cả xe
        cursor.execute("SELECT * FROM vehicles ORDER BY entry_time DESC")
        vehicles = [dict(row) for row in cursor.fetchall()]
        
        # Lấy tất cả slot
        cursor.execute("SELECT * FROM parking_slots ORDER BY floor, slot_code")
        slots = [dict(row) for row in cursor.fetchall()]
        
        # Lấy thống kê
        cursor.execute("SELECT COUNT(*) as total_vehicles FROM vehicles")
        total_vehicles = cursor.fetchone()['total_vehicles']
        
        cursor.execute("SELECT COUNT(*) as parked_vehicles FROM vehicles WHERE status = 'parked'")
        parked_vehicles = cursor.fetchone()['parked_vehicles']
        
        cursor.execute("SELECT COUNT(*) as available_slots FROM parking_slots WHERE is_occupied = 0")
        available_slots = cursor.fetchone()['available_slots']
        
        conn.close()
        
        export_data = {
            'export_time': datetime.now().isoformat(),
            'summary': {
                'total_vehicles': total_vehicles,
                'parked_vehicles': parked_vehicles,
                'available_slots': available_slots,
                'total_slots': 60
            },
            'vehicles': vehicles,
            'parking_slots': slots
        }
        
        return export_data
    
    def get_all_parked_vehicles(self):
        """Lấy tất cả xe đang đỗ"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                v.id,
                v.license_plate,
                v.brand_corrected,
                v.model_corrected,
                v.weight,
                v.assigned_slot,
                v.entry_time,
                v.image_path,
                ps.floor
            FROM vehicles v
            LEFT JOIN parking_slots ps ON v.assigned_slot = ps.slot_code
            WHERE v.status = 'parked'
            ORDER BY v.entry_time DESC
        ''')
        
        vehicles = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return vehicles
    
    def get_vehicle_by_id(self, vehicle_id):
        """Lấy thông tin chi tiết xe theo ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                v.*,
                ps.floor
            FROM vehicles v
            LEFT JOIN parking_slots ps ON v.assigned_slot = ps.slot_code
            WHERE v.id = ?
        ''', (vehicle_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def delete_vehicle(self, vehicle_id):
        """Xóa xe khỏi hệ thống"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Lấy thông tin xe
            cursor.execute("SELECT assigned_slot FROM vehicles WHERE id = ?", (vehicle_id,))
            vehicle = cursor.fetchone()
            
            if not vehicle:
                conn.close()
                return False
            
            slot_code = vehicle[0]
            
            # Xóa xe
            cursor.execute("DELETE FROM vehicles WHERE id = ?", (vehicle_id,))
            
            # Giải phóng slot
            cursor.execute('''
                UPDATE parking_slots 
                SET is_occupied = 0, vehicle_id = NULL 
                WHERE slot_code = ?
            ''', (slot_code,))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"Error deleting vehicle: {e}")
            return False
    
    def get_system_statistics(self):
        """Lấy thống kê hệ thống"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Tổng số xe đã xử lý
        cursor.execute("SELECT COUNT(*) as total_processed FROM vehicles")
        total_processed = cursor.fetchone()['total_processed']
        
        # Xe đang đỗ
        cursor.execute("SELECT COUNT(*) as current_parked FROM vehicles WHERE status = 'parked'")
        current_parked = cursor.fetchone()['current_parked']
        
        # Slot trống
        cursor.execute("SELECT COUNT(*) as available_slots FROM parking_slots WHERE is_occupied = 0")
        available_slots = cursor.fetchone()['available_slots']
        
        # Xe vào hôm nay
        today = datetime.now().date()
        cursor.execute('''
            SELECT COUNT(*) as today_entries 
            FROM vehicles 
            WHERE DATE(entry_time) = ?
        ''', (today,))
        today_entries = cursor.fetchone()['today_entries']
        
        conn.close()
        
        return {
            'total_processed': total_processed,
            'current_parked': current_parked,
            'available_slots': available_slots,
            'today_entries': today_entries
        }