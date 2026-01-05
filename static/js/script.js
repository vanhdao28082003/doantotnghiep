// Configuration
const API_BASE = 'http://localhost:5000/api';
let currentVehicle = null;

// DOM Elements
const fileInput = document.getElementById('fileInput');
const uploadArea = document.getElementById('uploadArea');
const previewImage = document.getElementById('previewImage');
const noPreview = document.getElementById('noPreview');
const processBtn = document.getElementById('processBtn');

// Drag and drop functionality
uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.style.borderColor = '#667eea';
    uploadArea.style.background = '#f7fafc';
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.style.borderColor = '#cbd5e0';
    uploadArea.style.background = '';
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.style.borderColor = '#cbd5e0';
    uploadArea.style.background = '';
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFileSelect(files[0]);
    }
});

// File input change
fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleFileSelect(e.target.files[0]);
    }
});

// Handle file selection
function handleFileSelect(file) {
    if (!file.type.match('image.*')) {
        showNotification('Please select an image file', 'error');
        return;
    }
    
    if (file.size > 16 * 1024 * 1024) {
        showNotification('File size must be less than 16MB', 'error');
        return;
    }
    
    const reader = new FileReader();
    reader.onload = function(e) {
        previewImage.src = e.target.result;
        previewImage.style.display = 'block';
        noPreview.style.display = 'none';
        processBtn.disabled = false;
    };
    reader.readAsDataURL(file);
}

// Process image
processBtn.addEventListener('click', async () => {
    if (!fileInput.files[0]) return;
    
    const formData = new FormData();
    formData.append('image', fileInput.files[0]);
    
    // Show loading
    processBtn.innerHTML = '<div class="loading"></div> PROCESSING...';
    processBtn.disabled = true;
    
    try {
        const response = await fetch(`${API_BASE}/process`, {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result && result.success) {
            currentVehicle = result.data;
            displayResults(result.data);
            showNotification('Vehicle processed successfully!', 'success');
            await updateParkingStatus();
            await updateRecentActivity();
            
            // Enable action buttons
            document.getElementById('confirmBtn').disabled = false;
            document.getElementById('exitBtn').disabled = false;
        } else {
            showNotification((result && (result.error || result.message)) || 'Processing failed', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showNotification('Server error. Please try again.', 'error');
    } finally {
        processBtn.innerHTML = '<i class="fas fa-play"></i> PROCESS IMAGE';
        processBtn.disabled = false;
    }
});

// Display results
function displayResults(data) {
    const detection = data.detection || {};
    const vehicle = data.vehicle || {};
    const parking = data.parking || {};
    
    // Vehicle info
    document.getElementById('brandBefore').textContent = detection.brand_before || '-';
    document.getElementById('brandAfter').textContent = detection.brand_after || '-';
    document.getElementById('modelBefore').textContent = detection.model_before || '-';
    document.getElementById('modelAfter').textContent = detection.model_after || '-';
    document.getElementById('vehicleWeight').textContent = vehicle.weight || '-';
    document.getElementById('licensePlate').textContent = vehicle.license_plate || '-';
    
    // Parking info
    document.getElementById('parkingFloor').textContent = parking.floor ? `Floor ${parking.floor}` : '-';
    document.getElementById('parkingSlot').textContent = parking.slot || '-';
}

// Update parking status
async function updateParkingStatus() {
    try {
        const response = await fetch(`${API_BASE}/status`);
        const result = await response.json();
        
        if (result && result.success) {
            const status = result.data;
            
            // Update floor stats
            for (let floor = 1; floor <= 3; floor++) {
                const floorData = status[floor];
                if (!floorData) continue;
                
                document.getElementById(`floor${floor}Occupied`).textContent = floorData.occupied;
                document.getElementById(`floor${floor}Available`).textContent = floorData.available;
                
                // Update progress bars
                const percentage = floorData.total > 0 ? (floorData.occupied / floorData.total) * 100 : 0;
                document.getElementById(`floor${floor}Progress`).style.width = `${percentage}%`;
                document.getElementById(`floor${floor}Percent`).textContent = `${Math.round(percentage)}%`;
                
                // Update slots grid
                updateFloorSlots(floor, floorData.occupied_slots || []);
            }
            
            // Update total count
            const totalOccupied = (status[1].occupied || 0) + (status[2].occupied || 0) + (status[3].occupied || 0);
            document.getElementById('parkingCount').innerHTML = `
                <i class="fas fa-car"></i>
                <span>${totalOccupied}/60 Parked</span>
            `;
        }
    } catch (error) {
        console.error('Error updating status:', error);
    }
}

// Update floor slots
function updateFloorSlots(floor, occupiedSlots) {
    const slotGrid = document.getElementById(`slotsFloor${floor}`);
    if (!slotGrid) return;
    
    const floorPrefix = ['I', 'II', 'III'][floor - 1];
    slotGrid.innerHTML = '';
    
    // Create 20 slots
    for (let i = 0; i < 20; i++) {
        const slotCode = `${floorPrefix}.${String.fromCharCode(65 + i)}`;
        const slotData = (occupiedSlots || []).find(slot => slot.slot_code === slotCode);
        
        const slotDiv = document.createElement('div');
        slotDiv.className = `slot-item ${slotData ? 'occupied' : 'empty'}`;
        
        if (slotData) {
            slotDiv.innerHTML = `
                <div class="slot-code">${slotCode}</div>
                <div class="slot-info">${slotData.license_plate || 'Occupied'}</div>
            `;
        } else {
            slotDiv.innerHTML = `
                <div class="slot-code">${slotCode}</div>
                <div class="slot-info">Empty</div>
            `;
        }
        
        slotGrid.appendChild(slotDiv);
    }
}

// Update recent activity
async function updateRecentActivity() {
    try {
        const response = await fetch(`${API_BASE}/recent`);
        const result = await response.json();
        
        if (result && result.success) {
            const recentList = document.getElementById('recentList');
            const vehicles = result.data || [];
            
            if (vehicles.length === 0) {
                recentList.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-car"></i>
                        <p>No recent activity</p>
                    </div>
                `;
                return;
            }
            
            recentList.innerHTML = '';
            vehicles.forEach(vehicle => {
                const item = document.createElement('div');
                item.className = 'recent-item';
                const timeStr = vehicle.entry_time ? new Date(vehicle.entry_time).toLocaleString() : '';
                item.innerHTML = `
                    <div class="recent-time">${timeStr}</div>
                    <div class="recent-details">
                        <div>
                            <strong>${vehicle.brand_corrected || ''} ${vehicle.model_corrected || ''}</strong><br>
                            <small>${vehicle.license_plate || ''}</small>
                        </div>
                        <div class="slot-code">${vehicle.assigned_slot || ''}</div>
                    </div>
                `;
                recentList.appendChild(item);
            });
        }
    } catch (error) {
        console.error('Error updating recent activity:', error);
    }
}

// Tab switching
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const floor = btn.dataset.floor;
        
        // Update active tab
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        
        // Show correct content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        document.getElementById(`tab${floor}`).classList.add('active');
    });
});

// Confirm entry
document.getElementById('confirmBtn').addEventListener('click', () => {
    if (!currentVehicle) return;
    
    showNotification('Vehicle entry confirmed!', 'success');
    updateParkingStatus();
});

// Vehicle exit
document.getElementById('exitBtn').addEventListener('click', async () => {
    if (!currentVehicle || !currentVehicle.vehicle || !currentVehicle.vehicle.license_plate) {
        showNotification('No vehicle selected for exit', 'error');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/exit`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                license_plate: currentVehicle.vehicle.license_plate
            })
        });
        
        const result = await response.json();
        
        if (result && result.success) {
            showNotification('Vehicle exited successfully', 'success');
            currentVehicle = null;
            
            // Reset form
            fileInput.value = '';
            previewImage.style.display = 'none';
            noPreview.style.display = 'flex';
            processBtn.disabled = true;
            
            // Reset results
            document.querySelectorAll('.result-value').forEach(el => {
                el.textContent = '-';
            });
            
            // Disable action buttons
            document.getElementById('confirmBtn').disabled = true;
            document.getElementById('exitBtn').disabled = true;
            
            // Update status
            await updateParkingStatus();
            await updateRecentActivity();
        } else {
            showNotification((result && (result.error || result.message)) || 'Exit failed', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showNotification('Server error', 'error');
    }
});

// Show notification
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    // Show
    setTimeout(() => notification.classList.add('show'), 10);
    
    // Hide after 3 seconds
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Auto-refresh parking status every 10 seconds
setInterval(updateParkingStatus, 10000);

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    updateParkingStatus();
    updateRecentActivity();
    
    // Check if server is running
    fetch(`${API_BASE}/status`)
        .then(() => console.log('✅ Connected to server'))
        .catch(() => console.log('⚠️ Server not running'));
});

// ====== MANAGEMENT FUNCTIONS ======

// Clear History
document.getElementById('clearHistoryBtn').addEventListener('click', () => {
    showConfirmationModal(
        'Clear History',
        'Are you sure you want to clear all recent activity history? This action cannot be undone.',
        async () => {
            try {
                const response = await fetch('/api/clear-history', {
                    method: 'DELETE'
                });
                const result = await response.json();
                
                if (result.success) {
                    showNotification('History cleared successfully', 'success');
                    updateRecentActivity();
                    updateSystemStats();
                } else {
                    showNotification(result.error || 'Failed to clear history', 'error');
                }
            } catch (error) {
                console.error('Error clearing history:', error);
                showNotification('Server error', 'error');
            }
        }
    );
});

// Reset System
document.getElementById('resetSystemBtn').addEventListener('click', () => {
    showConfirmationModal(
        'Reset System',
        '⚠️ WARNING: This will reset the entire system, clear all vehicles and history. Are you sure?',
        async () => {
            try {
                const response = await fetch('/api/reset-system', {
                    method: 'POST'
                });
                const result = await response.json();
                
                if (result.success) {
                    showNotification('System reset successfully', 'success');
                    // Reset UI
                    currentVehicle = null;
                    document.querySelectorAll('.result-value').forEach(el => {
                        el.textContent = '-';
                    });
                    updateParkingStatus();
                    updateRecentActivity();
                    updateSystemStats();
                } else {
                    showNotification(result.error || 'Failed to reset system', 'error');
                }
            } catch (error) {
                console.error('Error resetting system:', error);
                showNotification('Server error', 'error');
            }
        }
    );
});

// Export Data
document.getElementById('exportDataBtn').addEventListener('click', async () => {
    try {
        const response = await fetch('/api/export-data');
        const blob = await response.blob();
        
        // Create download link
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `parking_data_${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        showNotification('Data exported successfully', 'success');
    } catch (error) {
        console.error('Error exporting data:', error);
        showNotification('Failed to export data', 'error');
    }
});

// View All Vehicles
document.getElementById('viewAllVehiclesBtn').addEventListener('click', async () => {
    try {
        const response = await fetch('/api/all-vehicles');
        const result = await response.json();
        
        if (result.success) {
            showAllVehiclesModal(result.data);
        } else {
            showNotification(result.error || 'Failed to load vehicles', 'error');
        }
    } catch (error) {
        console.error('Error loading vehicles:', error);
        showNotification('Server error', 'error');
    }
});

// Update System Stats
async function updateSystemStats() {
    try {
        const response = await fetch('/api/stats');
        const result = await response.json();
        
        if (result.success) {
            const stats = result.data;
            document.getElementById('totalProcessed').textContent = stats.total_processed || 0;
            document.getElementById('currentParked').textContent = stats.current_parked || 0;
            document.getElementById('availableSlots').textContent = stats.available_slots || 60;
            document.getElementById('todayEntries').textContent = stats.today_entries || 0;
        }
    } catch (error) {
        console.error('Error updating stats:', error);
    }
}

// Show Confirmation Modal
function showConfirmationModal(title, message, confirmCallback) {
    const modal = document.getElementById('confirmationModal');
    document.getElementById('modalTitle').textContent = title;
    document.getElementById('modalMessage').textContent = message;
    
    modal.style.display = 'flex';
    
    // Setup event listeners
    const cancelBtn = document.getElementById('modalCancelBtn');
    const confirmBtn = document.getElementById('modalConfirmBtn');
    const closeBtn = modal.querySelector('.close-modal');
    
    const closeModal = () => {
        modal.style.display = 'none';
        // Remove event listeners
        cancelBtn.onclick = null;
        confirmBtn.onclick = null;
        closeBtn.onclick = null;
        modal.onclick = null;
    };
    
    cancelBtn.onclick = closeModal;
    closeBtn.onclick = closeModal;
    
    confirmBtn.onclick = () => {
        closeModal();
        confirmCallback();
    };
    
    // Close modal when clicking outside
    modal.onclick = (e) => {
        if (e.target === modal) {
            closeModal();
        }
    };
}

// Show All Vehicles Modal
function showAllVehiclesModal(vehicles) {
    const modal = document.getElementById('allVehiclesModal');
    const listContainer = document.getElementById('allVehiclesList');
    
    if (!vehicles || vehicles.length === 0) {
        listContainer.innerHTML = '<p class="empty-state">No vehicles in parking</p>';
    } else {
        listContainer.innerHTML = vehicles.map(vehicle => `
            <div class="vehicle-list-item" data-vehicle-id="${vehicle.id}">
                <div class="vehicle-list-header">
                    <div class="vehicle-list-slot">${vehicle.assigned_slot}</div>
                    <div class="vehicle-list-time">${new Date(vehicle.entry_time).toLocaleString()}</div>
                </div>
                <div><strong>${vehicle.brand_corrected} ${vehicle.model_corrected}</strong></div>
                <div class="vehicle-list-details">
                    <div class="vehicle-list-detail"><span>License:</span> ${vehicle.license_plate}</div>
                    <div class="vehicle-list-detail"><span>Weight:</span> ${vehicle.weight} kg</div>
                    <div class="vehicle-list-detail"><span>Floor:</span> ${vehicle.floor || 'N/A'}</div>
                </div>
            </div>
        `).join('');
        
        // Add click event to each vehicle item
        listContainer.querySelectorAll('.vehicle-list-item').forEach(item => {
            item.addEventListener('click', () => {
                const vehicleId = item.dataset.vehicleId;
                showVehicleDetailsModal(vehicleId);
            });
        });
    }
    
    modal.style.display = 'flex';
    
    // Setup close event
    const closeBtn = modal.querySelector('.close-modal');
    const closeAllBtn = document.getElementById('closeAllVehiclesBtn');
    
    const closeModal = () => {
        modal.style.display = 'none';
    };
    
    closeBtn.onclick = closeModal;
    closeAllBtn.onclick = closeModal;
    
    // Close when clicking outside
    modal.onclick = (e) => {
        if (e.target === modal) {
            closeModal();
        }
    };
}

// Show Vehicle Details Modal
async function showVehicleDetailsModal(vehicleId) {
    try {
        const response = await fetch(`/api/vehicle/${vehicleId}`);
        const result = await response.json();
        
        if (result.success) {
            const vehicle = result.data;
            const modal = document.getElementById('vehicleDetailsModal');
            const content = document.getElementById('vehicleDetailsContent');
            
            content.innerHTML = `
                <div class="vehicle-detail-row">
                    <span class="vehicle-detail-label">License Plate:</span>
                    <span class="vehicle-detail-value">${vehicle.license_plate}</span>
                </div>
                <div class="vehicle-detail-row">
                    <span class="vehicle-detail-label">Brand:</span>
                    <span class="vehicle-detail-value">${vehicle.brand_corrected}</span>
                </div>
                <div class="vehicle-detail-row">
                    <span class="vehicle-detail-label">Model:</span>
                    <span class="vehicle-detail-value">${vehicle.model_corrected}</span>
                </div>
                <div class="vehicle-detail-row">
                    <span class="vehicle-detail-label">Weight:</span>
                    <span class="vehicle-detail-value">${vehicle.weight} kg</span>
                </div>
                <div class="vehicle-detail-row">
                    <span class="vehicle-detail-label">Parking Slot:</span>
                    <span class="vehicle-detail-value">${vehicle.assigned_slot}</span>
                </div>
                <div class="vehicle-detail-row">
                    <span class="vehicle-detail-label">Floor:</span>
                    <span class="vehicle-detail-value">${vehicle.floor || 'N/A'}</span>
                </div>
                <div class="vehicle-detail-row">
                    <span class="vehicle-detail-label">Entry Time:</span>
                    <span class="vehicle-detail-value">${new Date(vehicle.entry_time).toLocaleString()}</span>
                </div>
                ${vehicle.exit_time ? `
                <div class="vehicle-detail-row">
                    <span class="vehicle-detail-label">Exit Time:</span>
                    <span class="vehicle-detail-value">${new Date(vehicle.exit_time).toLocaleString()}</span>
                </div>
                ` : ''}
                ${vehicle.image_path ? `
                <div class="vehicle-detail-row">
                    <span class="vehicle-detail-label">Vehicle Image:</span>
                    <img src="/static/uploads/${vehicle.image_path}" alt="Vehicle" style="max-width: 200px; border-radius: 5px;">
                </div>
                ` : ''}
            `;
            
            modal.style.display = 'flex';
            
            // Setup delete button
            const deleteBtn = document.getElementById('deleteVehicleBtn');
            deleteBtn.onclick = () => {
                showConfirmationModal(
                    'Delete Vehicle',
                    `Are you sure you want to delete vehicle ${vehicle.license_plate}? This action cannot be undone.`,
                    async () => {
                        try {
                            const deleteResponse = await fetch(`/api/vehicle/${vehicleId}`, {
                                method: 'DELETE'
                            });
                            const deleteResult = await deleteResponse.json();
                            
                            if (deleteResult.success) {
                                showNotification('Vehicle deleted successfully', 'success');
                                modal.style.display = 'none';
                                updateParkingStatus();
                                updateRecentActivity();
                                updateSystemStats();
                            } else {
                                showNotification(deleteResult.error || 'Failed to delete vehicle', 'error');
                            }
                        } catch (error) {
                            console.error('Error deleting vehicle:', error);
                            showNotification('Server error', 'error');
                        }
                    }
                );
            };
            
            // Setup close events
            const closeBtn = modal.querySelector('.close-modal');
            const closeDetailsBtn = document.getElementById('closeDetailsBtn');
            
            const closeModal = () => {
                modal.style.display = 'none';
                deleteBtn.onclick = null;
                closeBtn.onclick = null;
                closeDetailsBtn.onclick = null;
            };
            
            closeBtn.onclick = closeModal;
            closeDetailsBtn.onclick = closeModal;
            
            // Close when clicking outside
            modal.onclick = (e) => {
                if (e.target === modal) {
                    closeModal();
                }
            };
            
        } else {
            showNotification(result.error || 'Failed to load vehicle details', 'error');
        }
    } catch (error) {
        console.error('Error loading vehicle details:', error);
        showNotification('Server error', 'error');
    }
}

// Initialize management features
document.addEventListener('DOMContentLoaded', () => {
    // Update stats on load
    updateSystemStats();
    
    // Update stats every 30 seconds
    setInterval(updateSystemStats, 30000);
});