package com.carrental.admin.dao;

import com.carrental.admin.model.DashboardStats;
import com.carrental.admin.util.DatabaseUtil;
import java.math.BigDecimal;
import java.sql.*;
import java.util.*;

public class DashboardDAO {
    
    public DashboardStats getDashboardStats() {
        DashboardStats stats = new DashboardStats();
        
        try (Connection conn = DatabaseUtil.getConnection()) {
            stats.setUserCount(countQuery(conn, "SELECT COUNT(*) FROM users WHERE role = 'user'"));
            stats.setVehicleCount(countQuery(conn, "SELECT COUNT(*) FROM vehicles"));
            stats.setBrandCount(countQuery(conn, "SELECT COUNT(*) FROM vehicle_brands"));
            stats.setBookingCount(countQuery(conn, "SELECT COUNT(*) FROM bookings"));
            stats.setTotalRevenue(revenueQuery(conn));
            stats.setNewQueries(countQuery(conn, "SELECT COUNT(*) FROM contact_queries WHERE status = 'new'"));
            stats.setSubscriberCount(countQuery(conn, "SELECT COUNT(*) FROM subscribers WHERE is_active = 1"));
            stats.setExtensionCount(countQuery(conn, "SELECT COUNT(*) FROM extension_requests WHERE status = 'pending'"));
            stats.setPendingVerifications(countQuery(conn, "SELECT COUNT(*) FROM verifications WHERE verification_status = 'pending'"));
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return stats;
    }
    
    public Map<String, Integer> getBookingTrend() {
        Map<String, Integer> trend = new LinkedHashMap<>();
        String query = "SELECT DATE_FORMAT(created_at, '%Y-%m') as month, COUNT(*) as count " +
                      "FROM bookings WHERE created_at >= DATE_SUB(NOW(), INTERVAL 6 MONTH) " +
                      "GROUP BY month ORDER BY month ASC";
        
        try (Connection conn = DatabaseUtil.getConnection();
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(query)) {
            
            while (rs.next()) {
                trend.put(rs.getString("month"), rs.getInt("count"));
            }
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return trend;
    }
    
    public Map<String, Double> getRevenueTrend() {
        Map<String, Double> trend = new LinkedHashMap<>();
        String query = "SELECT DATE_FORMAT(created_at, '%Y-%m') as month, COALESCE(SUM(total_amount), 0) as total " +
                      "FROM bookings WHERE created_at >= DATE_SUB(NOW(), INTERVAL 6 MONTH) " +
                      "AND status IN ('completed', 'active', 'confirmed') GROUP BY month ORDER BY month ASC";
        
        try (Connection conn = DatabaseUtil.getConnection();
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(query)) {
            
            while (rs.next()) {
                trend.put(rs.getString("month"), rs.getDouble("total"));
            }
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return trend;
    }
    
    private int countQuery(Connection conn, String query) {
        try (Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(query)) {
            if (rs.next()) return rs.getInt(1);
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return 0;
    }
    
    private BigDecimal revenueQuery(Connection conn) {
        String query = "SELECT COALESCE(SUM(total_amount), 0) FROM bookings " +
                      "WHERE status IN ('completed', 'active', 'confirmed')";
        try (Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(query)) {
            if (rs.next()) return rs.getBigDecimal(1);
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return BigDecimal.ZERO;
    }
}