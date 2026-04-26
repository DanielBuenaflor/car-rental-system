package com.carrental.admin.dao;

import com.carrental.admin.model.Testimonial;
import com.carrental.admin.util.DatabaseUtil;
import java.sql.*;
import java.util.ArrayList;
import java.util.List;

public class TestimonialDAO {
    
    public List<Testimonial> getAllTestimonials() {
        List<Testimonial> list = new ArrayList<>();
        String query = "SELECT t.*, CONCAT(u.first_name, ' ', u.last_name) as user_name, u.email " +
                      "FROM testimonials t JOIN users u ON t.user_id = u.id ORDER BY t.created_at DESC";
        
        try (Connection conn = DatabaseUtil.getConnection();
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(query)) {
            
            while (rs.next()) {
                list.add(mapResultSetToTestimonial(rs));
            }
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return list;
    }
    
    public boolean updateStatus(int id, String status) {
        String query = "UPDATE testimonials SET status = ? WHERE id = ?";
        
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
    
    public int getPendingCount() {
        String query = "SELECT COUNT(*) as count FROM testimonials WHERE status = 'pending'";
        
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
    
    private Testimonial mapResultSetToTestimonial(ResultSet rs) throws SQLException {
        Testimonial t = new Testimonial();
        t.setId(rs.getInt("id"));
        t.setUserId(rs.getInt("user_id"));
        t.setUserName(rs.getString("user_name"));
        t.setUserEmail(rs.getString("email"));
        t.setRating(rs.getInt("rating"));
        t.setComment(rs.getString("comment"));
        t.setStatus(rs.getString("status"));
        t.setCreatedAt(rs.getTimestamp("created_at"));
        return t;
    }
}