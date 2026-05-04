package com.carrental.admin.ui;

import com.carrental.admin.dao.DashboardDAO;
import com.carrental.admin.model.DashboardStats;
import javax.swing.*;
import javax.swing.border.EmptyBorder;
import java.awt.*;
import java.util.Map;

public class DashboardPanel extends JPanel {
    private MainFrame mainFrame;
    private DashboardDAO dashboardDAO;
    private JLabel[] statValueLabels;
    
     private final String[] statNames = {
        "Total Vehicles", "Total Bookings", "Total Revenue", "Total Users", 
        "Pending Verifications", "New Queries", "Subscribers"
    };
    
    public DashboardPanel(MainFrame mainFrame) {
        this.mainFrame = mainFrame;
        this.dashboardDAO = new DashboardDAO();
        
        setLayout(new BorderLayout());
        setBackground(new Color(248, 250, 252));
        setBorder(new EmptyBorder(30, 30, 30, 30));
        
        initComponents();
    }
    
    private void initComponents() {
        JLabel titleLabel = new JLabel("Dashboard");
        titleLabel.setFont(new Font("Arial", Font.BOLD, 28));
        titleLabel.setForeground(new Color(31, 58, 95));
        
        JPanel topPanel = new JPanel(new BorderLayout());
        topPanel.setBackground(new Color(248, 250, 252));
        topPanel.add(titleLabel, BorderLayout.WEST);
        
        JButton refreshBtn = new JButton("Refresh");
        refreshBtn.setFont(new Font("Arial", Font.BOLD, 14));
        refreshBtn.setForeground(Color.WHITE);
        refreshBtn.setBackground(new Color(139, 92, 246));
        refreshBtn.setFocusPainted(false);
        refreshBtn.setCursor(Cursor.getPredefinedCursor(Cursor.HAND_CURSOR));
        refreshBtn.addActionListener(e -> refresh());
        
        JPanel btnPanel = new JPanel(new FlowLayout(FlowLayout.RIGHT));
        btnPanel.setBackground(new Color(248, 250, 252));
        btnPanel.add(refreshBtn);
        
        topPanel.add(btnPanel, BorderLayout.EAST);
        
        add(topPanel, BorderLayout.NORTH);
        
        JPanel mainContent = new JPanel(new BorderLayout(30, 30));
        mainContent.setBackground(new Color(248, 250, 252));
        
        JPanel statsGrid = createStatsPanel();
        mainContent.add(statsGrid, BorderLayout.NORTH);
        
        JPanel infoPanel = createInfoPanel();
        mainContent.add(infoPanel, BorderLayout.CENTER);
        
        add(mainContent, BorderLayout.CENTER);
    }
    
    private JPanel createStatsPanel() {
        JPanel statsPanel = new JPanel(new GridLayout(1, 8, 20, 20));
        statsPanel.setBackground(new Color(248, 250, 252));
        statsPanel.setBorder(new EmptyBorder(0, 0, 30, 0));
        
        statValueLabels = new JLabel[statNames.length];
        Color[] colors = {
            new Color(15, 59, 111), new Color(16, 185, 129), new Color(245, 158, 66),
            new Color(139, 92, 246), new Color(239, 68, 68),
            new Color(99, 102, 241), new Color(236, 72, 153)
        };
        
        statValueLabels = new JLabel[statNames.length];
        
        for (int i = 0; i < statNames.length; i++) {
            statValueLabels[i] = new JLabel("0");
            statValueLabels[i].setFont(new Font("Arial", Font.BOLD, 32));
            statValueLabels[i].setForeground(colors[i]);
            statValueLabels[i].setAlignmentX(Component.CENTER_ALIGNMENT);
            statValueLabels[i].setHorizontalAlignment(SwingConstants.CENTER);
            
            JLabel nameLabel = new JLabel(statNames[i]);
            nameLabel.setFont(new Font("Arial", Font.PLAIN, 14));
            nameLabel.setForeground(new Color(100, 116, 139));
            nameLabel.setAlignmentX(Component.CENTER_ALIGNMENT);
            nameLabel.setHorizontalAlignment(SwingConstants.CENTER);
            
            JPanel card = new JPanel();
            card.setLayout(new BoxLayout(card, BoxLayout.Y_AXIS));
            card.setBackground(Color.WHITE);
            card.setBorder(BorderFactory.createLineBorder(new Color(226, 232, 240)));
            card.setAlignmentX(Component.CENTER_ALIGNMENT);
            
            card.add(Box.createVerticalStrut(20));
            card.add(statValueLabels[i]);
            card.add(Box.createVerticalStrut(10));
            card.add(nameLabel);
            card.add(Box.createVerticalStrut(20));
            
            statsPanel.add(card);
        }
        
        return statsPanel;
    }
    
    private JPanel createInfoPanel() {
        JPanel infoPanel = new JPanel(new BorderLayout());
        infoPanel.setBackground(Color.WHITE);
        infoPanel.setBorder(BorderFactory.createLineBorder(new Color(226, 232, 240)));
        
        JLabel infoTitle = new JLabel("Quick Actions");
        infoTitle.setFont(new Font("Arial", Font.BOLD, 18));
        infoTitle.setForeground(new Color(31, 58, 95));
        infoTitle.setBorder(new EmptyBorder(20, 20, 20, 20));
        infoPanel.add(infoTitle, BorderLayout.NORTH);
        
        JPanel actionsPanel = new JPanel(new GridLayout(0, 3, 15, 15));
        actionsPanel.setBorder(new EmptyBorder(20, 20, 20, 20));
        
        actionsPanel.add(createActionButton("Manage Vehicles", "🚗"));
        actionsPanel.add(createActionButton("View Bookings", "📅"));
        actionsPanel.add(createActionButton("User Verifications", "📋"));
        actionsPanel.add(createActionButton("Vehicle Brands", "🏷️"));
        actionsPanel.add(createActionButton("Contact Queries", "📧"));
        
        infoPanel.add(actionsPanel, BorderLayout.CENTER);
        
        return infoPanel;
    }
    
    private JPanel createActionButton(String text, String icon) {
        JPanel btnPanel = new JPanel(new BorderLayout());
        btnPanel.setBackground(new Color(248, 250, 252));
        btnPanel.setCursor(Cursor.getPredefinedCursor(Cursor.HAND_CURSOR));
        
        JLabel label = new JLabel(icon + "  " + text);
        label.setFont(new Font("Arial", Font.PLAIN, 16));
        label.setForeground(new Color(15, 59, 111));
        
        JLabel countLabel = new JLabel("→");
        countLabel.setFont(new Font("Arial", Font.BOLD, 20));
        countLabel.setForeground(new Color(15, 59, 111));
        
        btnPanel.add(label, BorderLayout.CENTER);
        btnPanel.add(countLabel, BorderLayout.EAST);
        
        return btnPanel;
    }
    
    public void refresh() {
        try {
            DashboardStats stats = dashboardDAO.getDashboardStats();
            
            statValueLabels[0].setText(String.valueOf(stats.getVehicleCount()));
            statValueLabels[1].setText(String.valueOf(stats.getBookingCount()));
            statValueLabels[2].setText("₱" + String.format("%.0f", stats.getTotalRevenue()));
            statValueLabels[3].setText(String.valueOf(stats.getUserCount()));
            statValueLabels[4].setText(String.valueOf(stats.getPendingVerifications()));
            statValueLabels[5].setText(String.valueOf(stats.getNewQueries()));
            statValueLabels[6].setText(String.valueOf(stats.getSubscriberCount()));
            
        } catch (Exception e) {
            e.printStackTrace();
            JOptionPane.showMessageDialog(mainFrame, 
                "Error loading dashboard: " + e.getMessage(), "Error",
                JOptionPane.ERROR_MESSAGE);
        }
    }
}