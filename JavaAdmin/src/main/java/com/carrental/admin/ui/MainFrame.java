package com.carrental.admin.ui;

import javax.swing.*;
import java.awt.*;
import java.awt.event.*;

public class MainFrame extends JFrame {
    private JPanel contentPanel;
    private CardLayout cardLayout;
    
    private DashboardPanel dashboardPanel;
    private VehiclesPanel vehiclesPanel;
    private BookingsPanel bookingsPanel;
    private UsersPanel usersPanel;
    private VerificationsPanel verificationsPanel;
    private BrandsPanel brandsPanel;
    private TestimonialsPanel testimonialsPanel;
    private QueriesPanel queriesPanel;
    private SubscribersPanel subscribersPanel;
    
    public MainFrame() {
        setTitle("Car Rental Admin - Desktop Application");
        setSize(1400, 900);
        setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        setLocationRelativeTo(null);
        
        initComponents();
        loadDashboard();
    }
    
    private void initComponents() {
        setLayout(new BorderLayout());
        
        JPanel sidebar = createSidebar();
        add(sidebar, BorderLayout.WEST);
        
        contentPanel = new JPanel();
        cardLayout = new CardLayout();
        contentPanel.setLayout(cardLayout);
        contentPanel.setBackground(new Color(248, 250, 252));
        
        dashboardPanel = new DashboardPanel(this);
        vehiclesPanel = new VehiclesPanel(this);
        bookingsPanel = new BookingsPanel(this);
        usersPanel = new UsersPanel(this);
        verificationsPanel = new VerificationsPanel(this);
        brandsPanel = new BrandsPanel(this);
        testimonialsPanel = new TestimonialsPanel(this);
        queriesPanel = new QueriesPanel(this);
        subscribersPanel = new SubscribersPanel(this);
        
        contentPanel.add(dashboardPanel, "dashboard");
        contentPanel.add(vehiclesPanel, "vehicles");
        contentPanel.add(bookingsPanel, "bookings");
        contentPanel.add(usersPanel, "users");
        contentPanel.add(verificationsPanel, "verifications");
        contentPanel.add(brandsPanel, "brands");
        contentPanel.add(testimonialsPanel, "testimonials");
        contentPanel.add(queriesPanel, "queries");
        contentPanel.add(subscribersPanel, "subscribers");
        
        add(contentPanel, BorderLayout.CENTER);
    }
    
    private JPanel createSidebar() {
        JPanel sidebar = new JPanel();
        sidebar.setLayout(new BoxLayout(sidebar, BoxLayout.Y_AXIS));
        sidebar.setBackground(new Color(15, 59, 111));
        sidebar.setPreferredSize(new Dimension(260, getHeight()));
        sidebar.setBorder(BorderFactory.createEmptyBorder(20, 0, 20, 0));
        
        JLabel titleLabel = new JLabel("CAR RENTAL");
        titleLabel.setFont(new Font("Arial", Font.BOLD, 22));
        titleLabel.setForeground(Color.WHITE);
        titleLabel.setAlignmentX(Component.CENTER_ALIGNMENT);
        titleLabel.setBorder(BorderFactory.createEmptyBorder(0, 0, 30, 0));
        
        JLabel adminLabel = new JLabel("ADMIN");
        adminLabel.setFont(new Font("Arial", Font.BOLD, 18));
        adminLabel.setForeground(new Color(200, 200, 200));
        adminLabel.setAlignmentX(Component.CENTER_ALIGNMENT);
        adminLabel.setBorder(BorderFactory.createEmptyBorder(0, 0, 40, 0));
        
        sidebar.add(titleLabel);
        sidebar.add(adminLabel);
        
        String[] menuItems = {
            "Dashboard", "Vehicles", "Bookings", "Users",
            "Verifications", "Brands", "Testimonials", 
            "Queries", "Subscribers"
        };
        
        String[] icons = {
            "📊", "🚗", "📅", "👥",
            "📋", "🏷️", "⭐", "📧", "🔔"
        };
        
        for (int i = 0; i < menuItems.length; i++) {
            JButton btn = createMenuButton(menuItems[i], icons[i]);
            final String panelName = menuItems[i].toLowerCase();
            btn.addActionListener(e -> showPanel(panelName));
            sidebar.add(btn);
            sidebar.add(Box.createVerticalStrut(5));
        }
        
        sidebar.add(Box.createVerticalGlue());
        
        JButton logoutBtn = createMenuButton("Logout", "🚪");
        logoutBtn.addActionListener(e -> {
            int result = JOptionPane.showConfirmDialog(this, 
                "Are you sure you want to logout?", "Confirm Logout",
                JOptionPane.YES_NO_OPTION);
            if (result == JOptionPane.YES_OPTION) {
                System.exit(0);
            }
        });
        sidebar.add(logoutBtn);
        sidebar.add(Box.createVerticalStrut(20));
        
        return sidebar;
    }
    
    private JButton createMenuButton(String text, String icon) {
        JButton btn = new JButton(icon + "  " + text);
        btn.setFont(new Font("Arial", Font.PLAIN, 15));
        btn.setForeground(Color.WHITE);
        btn.setBackground(new Color(15, 59, 111));
        btn.setFocusPainted(false);
        btn.setBorderPainted(false);
        btn.setOpaque(true);
        btn.setMaximumSize(new Dimension(240, 45));
        btn.setMinimumSize(new Dimension(240, 45));
        btn.setPreferredSize(new Dimension(240, 45));
        btn.setCursor(Cursor.getPredefinedCursor(Cursor.HAND_CURSOR));
        btn.setAlignmentX(Component.CENTER_ALIGNMENT);
        
        btn.addMouseListener(new MouseAdapter() {
            @Override
            public void mouseEntered(MouseEvent e) {
                btn.setBackground(new Color(30, 74, 122));
            }
            
            @Override
            public void mouseExited(MouseEvent e) {
                btn.setBackground(new Color(15, 59, 111));
            }
        });
        
        return btn;
    }
    
    public void showPanel(String panelName) {
        cardLayout.show(contentPanel, panelName);
        
        switch (panelName) {
            case "dashboard": dashboardPanel.refresh(); break;
            case "vehicles": vehiclesPanel.refresh(); break;
            case "bookings": bookingsPanel.refresh(); break;
            case "users": usersPanel.refresh(); break;
            case "verifications": verificationsPanel.refresh(); break;
            case "brands": brandsPanel.refresh(); break;
            case "testimonials": testimonialsPanel.refresh(); break;
            case "queries": queriesPanel.refresh(); break;
            case "subscribers": subscribersPanel.refresh(); break;
        }
    }
    
    private void loadDashboard() {
        showPanel("dashboard");
    }
}