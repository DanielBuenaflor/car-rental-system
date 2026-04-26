package com.carrental.admin.model;

import java.sql.Date;
import java.sql.Timestamp;

public class Verification {
    private int id;
    private int userId;
    private String userName;
    private String userEmail;
    private String userPhone;
    private String licenseNumber;
    private Date licenseExpiryDate;
    private String licenseFrontImage;
    private String licenseBackImage;
    private String idCardType;
    private String idCardNumber;
    private String idCardImage;
    private String selfieImage;
    private String verificationStatus;
    private String rejectionReason;
    private Integer verifiedBy;
    private Timestamp verifiedAt;
    private Double ocrConfidenceScore;
    private Timestamp createdAt;
    private Timestamp updatedAt;

    public Verification() {}

    public int getId() { return id; }
    public void setId(int id) { this.id = id; }
    public int getUserId() { return userId; }
    public void setUserId(int userId) { this.userId = userId; }
    public String getUserName() { return userName; }
    public void setUserName(String userName) { this.userName = userName; }
    public String getUserEmail() { return userEmail; }
    public void setUserEmail(String userEmail) { this.userEmail = userEmail; }
    public String getUserPhone() { return userPhone; }
    public void setUserPhone(String userPhone) { this.userPhone = userPhone; }
    public String getLicenseNumber() { return licenseNumber; }
    public void setLicenseNumber(String licenseNumber) { this.licenseNumber = licenseNumber; }
    public Date getLicenseExpiryDate() { return licenseExpiryDate; }
    public void setLicenseExpiryDate(Date licenseExpiryDate) { this.licenseExpiryDate = licenseExpiryDate; }
    public String getLicenseFrontImage() { return licenseFrontImage; }
    public void setLicenseFrontImage(String licenseFrontImage) { this.licenseFrontImage = licenseFrontImage; }
    public String getLicenseBackImage() { return licenseBackImage; }
    public void setLicenseBackImage(String licenseBackImage) { this.licenseBackImage = licenseBackImage; }
    public String getIdCardType() { return idCardType; }
    public void setIdCardType(String idCardType) { this.idCardType = idCardType; }
    public String getIdCardNumber() { return idCardNumber; }
    public void setIdCardNumber(String idCardNumber) { this.idCardNumber = idCardNumber; }
    public String getIdCardImage() { return idCardImage; }
    public void setIdCardImage(String idCardImage) { this.idCardImage = idCardImage; }
    public String getSelfieImage() { return selfieImage; }
    public void setSelfieImage(String selfieImage) { this.selfieImage = selfieImage; }
    public String getVerificationStatus() { return verificationStatus; }
    public void setVerificationStatus(String verificationStatus) { this.verificationStatus = verificationStatus; }
    public String getRejectionReason() { return rejectionReason; }
    public void setRejectionReason(String rejectionReason) { this.rejectionReason = rejectionReason; }
    public Integer getVerifiedBy() { return verifiedBy; }
    public void setVerifiedBy(Integer verifiedBy) { this.verifiedBy = verifiedBy; }
    public Timestamp getVerifiedAt() { return verifiedAt; }
    public void setVerifiedAt(Timestamp verifiedAt) { this.verifiedAt = verifiedAt; }
    public Double getOcrConfidenceScore() { return ocrConfidenceScore; }
    public void setOcrConfidenceScore(Double ocrConfidenceScore) { this.ocrConfidenceScore = ocrConfidenceScore; }
    public Timestamp getCreatedAt() { return createdAt; }
    public void setCreatedAt(Timestamp createdAt) { this.createdAt = createdAt; }
    public Timestamp getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(Timestamp updatedAt) { this.updatedAt = updatedAt; }
}