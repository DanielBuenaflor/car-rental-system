package com.carrental.admin.dao;

import com.carrental.admin.model.Verification;
import com.carrental.admin.util.DatabaseUtil;
import java.sql.*;
import java.util.ArrayList;
import java.util.List;

public class VerificationDAO {
    
    public List<Verification> getAllVerifications() {
        List<Verification> list = new ArrayList<>();
        String query = "SELECT v.*, CONCAT(u.first_name, ' ', u.last_name) as user_name, u.email, u.phone " +
                      "FROM verifications v JOIN users u ON v.user_id = u.id ORDER BY v.created_at DESC";
        
        try (Connection conn = DatabaseUtil.getConnection();
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(query)) {
            
            while (rs.next()) {
                list.add(mapResultSetToVerification(rs));
            }
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return list;
    }
    
    public boolean updateVerificationStatus(int id, String status, String reason) {
        String query = "UPDATE verifications SET verification_status = ?, rejection_reason = ?, " +
                      "verified_at = NOW() WHERE id = ?";
        
        try (Connection conn = DatabaseUtil.getConnection();
             PreparedStatement pstmt = conn.prepareStatement(query)) {
            
            pstmt.setString(1, status);
            pstmt.setString(2, reason);
            pstmt.setInt(3, id);
            return pstmt.executeUpdate() > 0;
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return false;
    }
    
    public int getPendingCount() {
        String query = "SELECT COUNT(*) as count FROM verifications WHERE verification_status = 'pending'";
        
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
    
    private Verification mapResultSetToVerification(ResultSet rs) throws SQLException {
        Verification v = new Verification();
        v.setId(rs.getInt("id"));
        v.setUserId(rs.getInt("user_id"));
        v.setUserName(rs.getString("user_name"));
        v.setUserEmail(rs.getString("email"));
        v.setUserPhone(rs.getString("phone"));
        v.setLicenseNumber(rs.getString("license_number"));
        v.setLicenseExpiryDate(rs.getDate("license_expiry_date"));
        v.setLicenseFrontImage(rs.getString("license_front_image"));
        v.setLicenseBackImage(rs.getString("license_back_image"));
        v.setIdCardType(rs.getString("id_card_type"));
        v.setIdCardNumber(rs.getString("id_card_number"));
        v.setIdCardImage(rs.getString("id_card_image"));
        v.setSelfieImage(rs.getString("selfie_image"));
        v.setVerificationStatus(rs.getString("verification_status"));
        v.setRejectionReason(rs.getString("rejection_reason"));
        v.setVerifiedBy(rs.getObject("verified_by") != null ? rs.getInt("verified_by") : null);
        v.setVerifiedAt(rs.getTimestamp("verified_at"));
        v.setOcrConfidenceScore(rs.getObject("ocr_confidence_score") != null ? rs.getDouble("ocr_confidence_score") : null);
        v.setCreatedAt(rs.getTimestamp("created_at"));
        v.setUpdatedAt(rs.getTimestamp("updated_at"));
        return v;
    }
}