package com.carrental.admin.model;

import java.math.BigDecimal;

public class DashboardStats {
    private int userCount;
    private int vehicleCount;
    private int brandCount;
    private int bookingCount;
    private BigDecimal totalRevenue;
    private int pendingTestimonials;
    private int newQueries;
    private int subscriberCount;
    private int extensionCount;
    private int pendingVerifications;

    public DashboardStats() {}

    public int getUserCount() { return userCount; }
    public void setUserCount(int userCount) { this.userCount = userCount; }
    public int getVehicleCount() { return vehicleCount; }
    public void setVehicleCount(int vehicleCount) { this.vehicleCount = vehicleCount; }
    public int getBrandCount() { return brandCount; }
    public void setBrandCount(int brandCount) { this.brandCount = brandCount; }
    public int getBookingCount() { return bookingCount; }
    public void setBookingCount(int bookingCount) { this.bookingCount = bookingCount; }
    public BigDecimal getTotalRevenue() { return totalRevenue; }
    public void setTotalRevenue(BigDecimal totalRevenue) { this.totalRevenue = totalRevenue; }
    public int getPendingTestimonials() { return pendingTestimonials; }
    public void setPendingTestimonials(int pendingTestimonials) { this.pendingTestimonials = pendingTestimonials; }
    public int getNewQueries() { return newQueries; }
    public void setNewQueries(int newQueries) { this.newQueries = newQueries; }
    public int getSubscriberCount() { return subscriberCount; }
    public void setSubscriberCount(int subscriberCount) { this.subscriberCount = subscriberCount; }
    public int getExtensionCount() { return extensionCount; }
    public void setExtensionCount(int extensionCount) { this.extensionCount = extensionCount; }
    public int getPendingVerifications() { return pendingVerifications; }
    public void setPendingVerifications(int pendingVerifications) { this.pendingVerifications = pendingVerifications; }
}