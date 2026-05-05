package com.carrental.admin.dao;

import com.carrental.admin.model.ContactQuery;
import com.carrental.admin.util.DatabaseUtil;
import java.sql.*;
import java.util.ArrayList;
import java.util.List;

public class ContactQueryDAO {
    
    public List<ContactQuery> getAllQueries() {
        List<ContactQuery> list = new ArrayList<>();
        String query = "SELECT q.*, CONCAT(u.first_name, ' ', u.last_name) as user_name " +
                      "FROM contact_queries q LEFT JOIN users u ON q.user_id = u.id ORDER BY q.created_at DESC";
        
        try (Connection conn = DatabaseUtil.getConnection();
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(query)) {
            
            while (rs.next()) {
                list.add(mapResultSetToQuery(rs));
            }
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return list;
    }
    
    public boolean replyToQuery(int id, String reply) {
        String query = "UPDATE contact_queries SET reply = ?, replied_at = NOW(), status = 'replied' WHERE id = ?";
        
        try (Connection conn = DatabaseUtil.getConnection();
             PreparedStatement pstmt = conn.prepareStatement(query)) {
            
            pstmt.setString(1, reply);
            pstmt.setInt(2, id);
            return pstmt.executeUpdate() > 0;
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return false;
    }
    
    public int getNewCount() {
        String query = "SELECT COUNT(*) as count FROM contact_queries WHERE status = 'new'";
        
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
    
    private ContactQuery mapResultSetToQuery(ResultSet rs) throws SQLException {
        ContactQuery q = new ContactQuery();
        q.setId(rs.getInt("id"));
        q.setUserId(rs.getObject("user_id") != null ? rs.getInt("user_id") : null);
        q.setUserName(rs.getString("user_name"));
        q.setName(rs.getString("name"));
        q.setEmail(rs.getString("email"));
        q.setPhone(rs.getString("phone"));
        q.setSubject(rs.getString("subject"));
        q.setMessage(rs.getString("message"));
        q.setStatus(rs.getString("status"));
        q.setReply(rs.getString("reply"));
        q.setRepliedAt(rs.getTimestamp("replied_at"));
        q.setCreatedAt(rs.getTimestamp("created_at"));
        return q;
    }
}