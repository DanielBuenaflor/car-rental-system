package com.carrental.admin.dao;

import com.carrental.admin.model.Brand;
import com.carrental.admin.util.DatabaseUtil;
import java.sql.*;
import java.util.ArrayList;
import java.util.List;

public class BrandDAO {
    
    public List<Brand> getAllBrands() {
        List<Brand> brands = new ArrayList<>();
        String query = "SELECT * FROM vehicle_brands ORDER BY name";
        
        try (Connection conn = DatabaseUtil.getConnection();
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(query)) {
            
            while (rs.next()) {
                brands.add(mapResultSetToBrand(rs));
            }
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return brands;
    }
    
    public boolean insertBrand(Brand brand) {
        String query = "INSERT INTO vehicle_brands (name, description, founded_year, country_of_origin) VALUES (?, ?, ?, ?)";
        
        try (Connection conn = DatabaseUtil.getConnection();
             PreparedStatement pstmt = conn.prepareStatement(query)) {
            
            pstmt.setString(1, brand.getName());
            pstmt.setString(2, brand.getDescription());
            pstmt.setObject(3, brand.getFoundedYear());
            pstmt.setString(4, brand.getCountryOfOrigin());
            
            return pstmt.executeUpdate() > 0;
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return false;
    }
    
    public boolean updateBrand(Brand brand) {
        String query = "UPDATE vehicle_brands SET name = ?, description = ?, founded_year = ?, country_of_origin = ? WHERE id = ?";
        
        try (Connection conn = DatabaseUtil.getConnection();
             PreparedStatement pstmt = conn.prepareStatement(query)) {
            
            pstmt.setString(1, brand.getName());
            pstmt.setString(2, brand.getDescription());
            pstmt.setObject(3, brand.getFoundedYear());
            pstmt.setString(4, brand.getCountryOfOrigin());
            pstmt.setInt(5, brand.getId());
            
            return pstmt.executeUpdate() > 0;
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return false;
    }
    
    public boolean deleteBrand(int id) {
        String query = "DELETE FROM vehicle_brands WHERE id = ?";
        
        try (Connection conn = DatabaseUtil.getConnection();
             PreparedStatement pstmt = conn.prepareStatement(query)) {
            
            pstmt.setInt(1, id);
            return pstmt.executeUpdate() > 0;
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return false;
    }
    
    public int getBrandCount() {
        String query = "SELECT COUNT(*) as count FROM vehicle_brands";
        
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
    
    private Brand mapResultSetToBrand(ResultSet rs) throws SQLException {
        Brand brand = new Brand();
        brand.setId(rs.getInt("id"));
        brand.setName(rs.getString("name"));
        brand.setLogo(rs.getString("logo"));
        brand.setDescription(rs.getString("description"));
        brand.setFoundedYear(rs.getObject("founded_year") != null ? rs.getInt("founded_year") : null);
        brand.setCountryOfOrigin(rs.getString("country_of_origin"));
        brand.setCreatedAt(rs.getTimestamp("created_at"));
        brand.setUpdatedAt(rs.getTimestamp("updated_at"));
        return brand;
    }
}