package com.carrental.admin.dao;

import com.carrental.admin.model.Booking;
import com.carrental.admin.util.DatabaseUtil;
import java.sql.*;
import java.util.ArrayList;
import java.util.List;

public class BookingDAO {
    
    public List<Booking> getAllBookings() {
        List<Booking> bookings = new ArrayList<>();
        String query = "SELECT b.*, CONCAT(u.first_name, ' ', u.last_name) as user_name, " +
                     "u.email as user_email, u.phone as user_phone, v.model, v.year, v.license_plate, " +
                     "v.daily_rate as daily_rate_applied, vb.name as brand_name " +
                     "FROM bookings b " +
                     "JOIN users u ON b.user_id = u.id " +
                     "JOIN vehicles v ON b.vehicle_id = v.id " +
                     "JOIN vehicle_brands vb ON v.brand_id = vb.id " +
                     "ORDER BY b.created_at DESC";
        
        try (Connection conn = DatabaseUtil.getConnection();
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(query)) {
            
            while (rs.next()) {
                bookings.add(mapResultSetToBooking(rs));
            }
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return bookings;
    }
    
    public Booking getBookingById(int id) {
        String query = "SELECT b.*, CONCAT(u.first_name, ' ', u.last_name) as user_name, " +
                     "u.email as user_email, u.phone as user_phone, v.model, v.year, v.license_plate, " +
                     "v.daily_rate as daily_rate_applied, vb.name as brand_name " +
                     "FROM bookings b " +
                     "JOIN users u ON b.user_id = u.id " +
                     "JOIN vehicles v ON b.vehicle_id = v.id " +
                     "JOIN vehicle_brands vb ON v.brand_id = vb.id " +
                     "WHERE b.id = ?";
        
        try (Connection conn = DatabaseUtil.getConnection();
             PreparedStatement pstmt = conn.prepareStatement(query)) {
            
            pstmt.setInt(1, id);
            try (ResultSet rs = pstmt.executeQuery()) {
                if (rs.next()) {
                    return mapResultSetToBooking(rs);
                }
            }
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return null;
    }
    
    public boolean updateBookingStatus(int id, String status) {
        String query = "UPDATE bookings SET status = ? WHERE id = ?";
        
        try (Connection conn = DatabaseUtil.getConnection();
             PreparedStatement pstmt = conn.prepareStatement(query)) {
            
            pstmt.setString(1, status);
            pstmt.setInt(2, id);
            return pstmt.executeUpdate() > 0;
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return false;
    }
    
    public boolean cancelBooking(int id, String reason) {
        String query = "UPDATE bookings SET status = 'cancelled', cancellation_reason = ?, " +
                     "cancelled_by = 'admin', cancelled_at = NOW() WHERE id = ?";
        
        try (Connection conn = DatabaseUtil.getConnection();
             PreparedStatement pstmt = conn.prepareStatement(query)) {
            
            pstmt.setString(1, reason);
            pstmt.setInt(2, id);
            return pstmt.executeUpdate() > 0;
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return false;
    }
    
    public int getBookingCount() {
        String query = "SELECT COUNT(*) as count FROM bookings";
        
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
    
    private Booking mapResultSetToBooking(ResultSet rs) throws SQLException {
        Booking booking = new Booking();
        booking.setId(rs.getInt("id"));
        booking.setBookingReference(rs.getString("booking_reference"));
        booking.setUserId(rs.getInt("user_id"));
        booking.setUserName(rs.getString("user_name"));
        booking.setUserEmail(rs.getString("user_email"));
        booking.setUserPhone(rs.getString("user_phone"));
        booking.setVehicleId(rs.getInt("vehicle_id"));
        booking.setVehicleModel(rs.getString("model"));
        booking.setVehicleBrand(rs.getString("brand_name"));
        booking.setVehicleYear(rs.getInt("year"));
        booking.setLicensePlate(rs.getString("license_plate"));
        booking.setDailyRateApplied(rs.getBigDecimal("daily_rate_applied"));
        booking.setStartDate(rs.getTimestamp("start_date"));
        booking.setEndDate(rs.getTimestamp("end_date"));
        booking.setActualReturnDate(rs.getTimestamp("actual_return_date"));
        booking.setPickupLocation(rs.getString("pickup_location"));
        booking.setReturnLocation(rs.getString("return_location"));
        booking.setRentalDays(rs.getObject("rental_days") != null ? rs.getInt("rental_days") : null);
        booking.setSubtotal(rs.getBigDecimal("subtotal"));
        booking.setTaxAmount(rs.getBigDecimal("tax_amount"));
        booking.setDiscountAmount(rs.getBigDecimal("discount_amount"));
        booking.setTotalAmount(rs.getBigDecimal("total_amount"));
        booking.setSecurityDeposit(rs.getBigDecimal("security_deposit"));
        booking.setDepositRefunded(rs.getBoolean("deposit_refunded"));
        booking.setPromotionCode(rs.getString("promotion_code"));
        booking.setStatus(rs.getString("status"));
        booking.setCancellationReason(rs.getString("cancellation_reason"));
        booking.setCancelledAt(rs.getTimestamp("cancelled_at"));
        booking.setNotes(rs.getString("notes"));
        booking.setCreatedAt(rs.getTimestamp("created_at"));
        booking.setUpdatedAt(rs.getTimestamp("updated_at"));
        return booking;
    }
}