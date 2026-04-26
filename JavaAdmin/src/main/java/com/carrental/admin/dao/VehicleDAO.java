package com.carrental.admin.dao;

import com.carrental.admin.model.Vehicle;
import com.carrental.admin.util.DatabaseUtil;
import java.sql.*;
import java.util.ArrayList;
import java.util.List;

public class VehicleDAO {
    
    public List<Vehicle> getAllVehicles() {
        List<Vehicle> vehicles = new ArrayList<>();
        String query = "SELECT v.*, vb.name as brand_name FROM vehicles v " +
                     "JOIN vehicle_brands vb ON v.brand_id = vb.id ORDER BY v.id DESC";
        
        try (Connection conn = DatabaseUtil.getConnection();
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(query)) {
            
            while (rs.next()) {
                vehicles.add(mapResultSetToVehicle(rs));
            }
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return vehicles;
    }
    
    public Vehicle getVehicleById(int id) {
        String query = "SELECT v.*, vb.name as brand_name FROM vehicles v " +
                     "JOIN vehicle_brands vb ON v.brand_id = vb.id WHERE v.id = ?";
        
        try (Connection conn = DatabaseUtil.getConnection();
             PreparedStatement pstmt = conn.prepareStatement(query)) {
            
            pstmt.setInt(1, id);
            try (ResultSet rs = pstmt.executeQuery()) {
                if (rs.next()) {
                    return mapResultSetToVehicle(rs);
                }
            }
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return null;
    }
    
    public boolean insertVehicle(Vehicle vehicle) {
        String query = "INSERT INTO vehicles (brand_id, model, year, license_plate, color, transmission, " +
                     "fuel_type, seating_capacity, daily_rate, weekly_rate, monthly_rate, " +
                     "security_deposit, mileage_limit_km, excess_km_charge, status, " +
                     "location, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)";
        
        try (Connection conn = DatabaseUtil.getConnection();
             PreparedStatement pstmt = conn.prepareStatement(query)) {
            
            pstmt.setInt(1, vehicle.getBrandId());
            pstmt.setString(2, vehicle.getModel());
            pstmt.setInt(3, vehicle.getYear());
            pstmt.setString(4, vehicle.getLicensePlate());
            pstmt.setString(5, vehicle.getColor());
            pstmt.setString(6, vehicle.getTransmission());
            pstmt.setString(7, vehicle.getFuelType());
            pstmt.setInt(8, vehicle.getSeatingCapacity());
            pstmt.setBigDecimal(9, vehicle.getDailyRate());
            pstmt.setBigDecimal(10, vehicle.getWeeklyRate());
            pstmt.setBigDecimal(11, vehicle.getMonthlyRate());
            pstmt.setBigDecimal(12, vehicle.getSecurityDeposit());
            pstmt.setInt(13, vehicle.getMileageLimitKm());
            pstmt.setBigDecimal(14, vehicle.getExcessKmCharge());
            pstmt.setString(15, vehicle.getStatus());
            pstmt.setString(16, vehicle.getLocation());
            pstmt.setString(17, vehicle.getDescription());
            
            return pstmt.executeUpdate() > 0;
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return false;
    }
    
    public boolean updateVehicle(Vehicle vehicle) {
        String query = "UPDATE vehicles SET brand_id = ?, model = ?, year = ?, license_plate = ?, " +
                     "color = ?, transmission = ?, fuel_type = ?, seating_capacity = ?, " +
                     "daily_rate = ?, weekly_rate = ?, monthly_rate = ?, " +
                     "security_deposit = ?, mileage_limit_km = ?, excess_km_charge = ?, " +
                     "status = ?, location = ?, description = ? WHERE id = ?";
        
        try (Connection conn = DatabaseUtil.getConnection();
             PreparedStatement pstmt = conn.prepareStatement(query)) {
            
            pstmt.setInt(1, vehicle.getBrandId());
            pstmt.setString(2, vehicle.getModel());
            pstmt.setInt(3, vehicle.getYear());
            pstmt.setString(4, vehicle.getLicensePlate());
            pstmt.setString(5, vehicle.getColor());
            pstmt.setString(6, vehicle.getTransmission());
            pstmt.setString(7, vehicle.getFuelType());
            pstmt.setInt(8, vehicle.getSeatingCapacity());
            pstmt.setBigDecimal(9, vehicle.getDailyRate());
            pstmt.setBigDecimal(10, vehicle.getWeeklyRate());
            pstmt.setBigDecimal(11, vehicle.getMonthlyRate());
            pstmt.setBigDecimal(12, vehicle.getSecurityDeposit());
            pstmt.setInt(13, vehicle.getMileageLimitKm());
            pstmt.setBigDecimal(14, vehicle.getExcessKmCharge());
            pstmt.setString(15, vehicle.getStatus());
            pstmt.setString(16, vehicle.getLocation());
            pstmt.setString(17, vehicle.getDescription());
            pstmt.setInt(18, vehicle.getId());
            
            return pstmt.executeUpdate() > 0;
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return false;
    }
    
    public boolean deleteVehicle(int id) {
        String query = "DELETE FROM vehicles WHERE id = ?";
        
        try (Connection conn = DatabaseUtil.getConnection();
             PreparedStatement pstmt = conn.prepareStatement(query)) {
            
            pstmt.setInt(1, id);
            return pstmt.executeUpdate() > 0;
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return false;
    }
    
    public int getVehicleCount() {
        String query = "SELECT COUNT(*) as count FROM vehicles";
        
        try (Connection conn = DatabaseUtil.getConnection();
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(query)) {
            
            if (rs.next()) {
                return rs.getInt("count");
            }
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return 0;
    }
    
    private Vehicle mapResultSetToVehicle(ResultSet rs) throws SQLException {
        Vehicle vehicle = new Vehicle();
        vehicle.setId(rs.getInt("id"));
        vehicle.setBrandId(rs.getInt("brand_id"));
        vehicle.setBrandName(rs.getString("brand_name"));
        vehicle.setModel(rs.getString("model"));
        vehicle.setYear(rs.getInt("year"));
        vehicle.setLicensePlate(rs.getString("license_plate"));
        vehicle.setColor(rs.getString("color"));
        vehicle.setTransmission(rs.getString("transmission"));
        vehicle.setFuelType(rs.getString("fuel_type"));
        vehicle.setSeatingCapacity(rs.getInt("seating_capacity"));
        vehicle.setDailyRate(rs.getBigDecimal("daily_rate"));
        vehicle.setWeeklyRate(rs.getBigDecimal("weekly_rate"));
        vehicle.setMonthlyRate(rs.getBigDecimal("monthly_rate"));
        vehicle.setSecurityDeposit(rs.getBigDecimal("security_deposit"));
        vehicle.setMileageLimitKm(rs.getInt("mileage_limit_km"));
        vehicle.setExcessKmCharge(rs.getBigDecimal("excess_km_charge"));
        vehicle.setStatus(rs.getString("status"));
        vehicle.setLocation(rs.getString("location"));
        vehicle.setDescription(rs.getString("description"));
        vehicle.setPrimaryImage(rs.getString("primary_image"));
        vehicle.setCurrentOdometer(rs.getObject("current_odometer") != null ? rs.getInt("current_odometer") : null);
        vehicle.setLastServiceDate(rs.getDate("last_service_date"));
        vehicle.setNextServiceDate(rs.getDate("next_service_date"));
        vehicle.setInsuranceExpiry(rs.getDate("insurance_expiry"));
        vehicle.setRegistrationExpiry(rs.getDate("registration_expiry"));
        vehicle.setCreatedAt(rs.getTimestamp("created_at"));
        vehicle.setUpdatedAt(rs.getTimestamp("updated_at"));
        return vehicle;
    }
}