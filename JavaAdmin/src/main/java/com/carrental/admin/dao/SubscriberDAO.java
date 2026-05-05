package com.carrental.admin.dao;

import com.carrental.admin.model.Subscriber;
import com.carrental.admin.util.DatabaseUtil;
import java.sql.*;
import java.util.ArrayList;
import java.util.List;

public class SubscriberDAO {
    
    public List<Subscriber> getAllSubscribers() {
        List<Subscriber> list = new ArrayList<>();
        String query = "SELECT * FROM subscribers ORDER BY subscribed_at DESC";
        
        try (Connection conn = DatabaseUtil.getConnection();
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(query)) {
            
            while (rs.next()) {
                Subscriber s = new Subscriber();
                s.setId(rs.getInt("id"));
                s.setEmail(rs.getString("email"));
                s.setActive(rs.getBoolean("is_active"));
                s.setSubscribedAt(rs.getTimestamp("subscribed_at"));
                s.setUnsubscribedAt(rs.getTimestamp("unsubscribed_at"));
                list.add(s);
            }
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return list;
    }
    
    public boolean updateStatus(int id, boolean active) {
        String query = "UPDATE subscribers SET is_active = ? WHERE id = ?";
        
        try (Connection conn = DatabaseUtil.getConnection();
             PreparedStatement pstmt = conn.prepareStatement(query)) {
            
            pstmt.setBoolean(1, active);
            pstmt.setInt(2, id);
            return pstmt.executeUpdate() > 0;
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return false;
    }
    
    public int getActiveCount() {
        String query = "SELECT COUNT(*) as count FROM subscribers WHERE is_active = 1";
        
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
}