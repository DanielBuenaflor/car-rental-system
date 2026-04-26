package com.carrental.admin.model;

import java.math.BigDecimal;
import java.sql.Date;
import java.sql.Timestamp;

public class Vehicle {
    private int id;
    private int brandId;
    private String brandName;
    private String model;
    private int year;
    private String licensePlate;
    private String color;
    private String transmission;
    private String fuelType;
    private int seatingCapacity;
    private BigDecimal dailyRate;
    private BigDecimal weeklyRate;
    private BigDecimal monthlyRate;
    private BigDecimal securityDeposit;
    private int mileageLimitKm;
    private BigDecimal excessKmCharge;
    private String status;
    private String location;
    private String description;
    private String primaryImage;
    private Integer currentOdometer;
    private Date lastServiceDate;
    private Date nextServiceDate;
    private Date insuranceExpiry;
    private Date registrationExpiry;
    private Timestamp createdAt;
    private Timestamp updatedAt;

    public Vehicle() {}

    public int getId() { return id; }
    public void setId(int id) { this.id = id; }
    public int getBrandId() { return brandId; }
    public void setBrandId(int brandId) { this.brandId = brandId; }
    public String getBrandName() { return brandName; }
    public void setBrandName(String brandName) { this.brandName = brandName; }
    public String getModel() { return model; }
    public void setModel(String model) { this.model = model; }
    public int getYear() { return year; }
    public void setYear(int year) { this.year = year; }
    public String getLicensePlate() { return licensePlate; }
    public void setLicensePlate(String licensePlate) { this.licensePlate = licensePlate; }
    public String getColor() { return color; }
    public void setColor(String color) { this.color = color; }
    public String getTransmission() { return transmission; }
    public void setTransmission(String transmission) { this.transmission = transmission; }
    public String getFuelType() { return fuelType; }
    public void setFuelType(String fuelType) { this.fuelType = fuelType; }
    public int getSeatingCapacity() { return seatingCapacity; }
    public void setSeatingCapacity(int seatingCapacity) { this.seatingCapacity = seatingCapacity; }
    public BigDecimal getDailyRate() { return dailyRate; }
    public void setDailyRate(BigDecimal dailyRate) { this.dailyRate = dailyRate; }
    public BigDecimal getWeeklyRate() { return weeklyRate; }
    public void setWeeklyRate(BigDecimal weeklyRate) { this.weeklyRate = weeklyRate; }
    public BigDecimal getMonthlyRate() { return monthlyRate; }
    public void setMonthlyRate(BigDecimal monthlyRate) { this.monthlyRate = monthlyRate; }
    public BigDecimal getSecurityDeposit() { return securityDeposit; }
    public void setSecurityDeposit(BigDecimal securityDeposit) { this.securityDeposit = securityDeposit; }
    public int getMileageLimitKm() { return mileageLimitKm; }
    public void setMileageLimitKm(int mileageLimitKm) { this.mileageLimitKm = mileageLimitKm; }
    public BigDecimal getExcessKmCharge() { return excessKmCharge; }
    public void setExcessKmCharge(BigDecimal excessKmCharge) { this.excessKmCharge = excessKmCharge; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getLocation() { return location; }
    public void setLocation(String location) { this.location = location; }
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
    public String getPrimaryImage() { return primaryImage; }
    public void setPrimaryImage(String primaryImage) { this.primaryImage = primaryImage; }
    public Integer getCurrentOdometer() { return currentOdometer; }
    public void setCurrentOdometer(Integer currentOdometer) { this.currentOdometer = currentOdometer; }
    public Date getLastServiceDate() { return lastServiceDate; }
    public void setLastServiceDate(Date lastServiceDate) { this.lastServiceDate = lastServiceDate; }
    public Date getNextServiceDate() { return nextServiceDate; }
    public void setNextServiceDate(Date nextServiceDate) { this.nextServiceDate = nextServiceDate; }
    public Date getInsuranceExpiry() { return insuranceExpiry; }
    public void setInsuranceExpiry(Date insuranceExpiry) { this.insuranceExpiry = insuranceExpiry; }
    public Date getRegistrationExpiry() { return registrationExpiry; }
    public void setRegistrationExpiry(Date registrationExpiry) { this.registrationExpiry = registrationExpiry; }
    public Timestamp getCreatedAt() { return createdAt; }
    public void setCreatedAt(Timestamp createdAt) { this.createdAt = createdAt; }
    public Timestamp getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(Timestamp updatedAt) { this.updatedAt = updatedAt; }

    public String getDisplayName() { return brandName + " " + model + " (" + year + ")"; }
}