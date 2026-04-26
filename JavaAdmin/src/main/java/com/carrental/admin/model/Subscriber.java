package com.carrental.admin.model;

import java.sql.Timestamp;

public class Subscriber {
    private int id;
    private String email;
    private boolean isActive;
    private Timestamp subscribedAt;
    private Timestamp unsubscribedAt;

    public Subscriber() {}

    public int getId() { return id; }
    public void setId(int id) { this.id = id; }
    public String getEmail() { return email; }
    public void setEmail(String email) { this.email = email; }
    public boolean isActive() { return isActive; }
    public void setActive(boolean active) { isActive = active; }
    public Timestamp getSubscribedAt() { return subscribedAt; }
    public void setSubscribedAt(Timestamp subscribedAt) { this.subscribedAt = subscribedAt; }
    public Timestamp getUnsubscribedAt() { return unsubscribedAt; }
    public void setUnsubscribedAt(Timestamp unsubscribedAt) { this.unsubscribedAt = unsubscribedAt; }
}