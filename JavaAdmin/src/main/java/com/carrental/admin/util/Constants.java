package com.carrental.admin.util;

import java.awt.Color;

public class Constants {
    
    // App Info
    public static final String APP_NAME = "Car Rental Admin";
    public static final String APP_VERSION = "1.0.0";
    
    // Database
    public static final String DB_URL = "jdbc:mysql://localhost:3306/car_rental_system";
    public static final String DB_DRIVER = "com.mysql.cj.jdbc.Driver";
    
    // Colors
    public static final Color PRIMARY_COLOR = new Color(15, 59, 111);
    public static final Color SECONDARY_COLOR = new Color(30, 74, 122);
    public static final Color SUCCESS_COLOR = new Color(16, 185, 129);
    public static final Color DANGER_COLOR = new Color(239, 68, 68);
    public static final Color WARNING_COLOR = new Color(245, 158, 11);
    
    // Booking Status
    public static final String STATUS_PENDING = "pending";
    public static final String STATUS_CONFIRMED = "confirmed";
    public static final String STATUS_ACTIVE = "active";
    public static final String STATUS_COMPLETED = "completed";
    public static final String STATUS_CANCELLED = "cancelled";
    
    // Verification Status
    public static final String VERIFICATION_PENDING = "pending";
    public static final String VERIFICATION_APPROVED = "approved";
    public static final String VERIFICATION_REJECTED = "rejected";
    
    // UI Constants
    public static final int FRAME_WIDTH = 1200;
    public static final int FRAME_HEIGHT = 800;
    public static final int PANEL_PADDING = 20;
    public static final int COMPONENT_HEIGHT = 35;
    
    private Constants() {
        // Utility class - no instantiation
    }
}