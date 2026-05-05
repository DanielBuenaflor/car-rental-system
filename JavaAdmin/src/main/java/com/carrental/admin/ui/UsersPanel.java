package com.carrental.admin.ui;

import com.carrental.admin.dao.UserDAO;
import com.carrental.admin.model.User;
import javax.swing.*;
import javax.swing.border.EmptyBorder;
import javax.swing.table.DefaultTableModel;
import java.awt.*;
import java.util.List;

public class UsersPanel extends JPanel {
    private MainFrame mainFrame;
    private UserDAO userDAO;
    private JTable table;
    private DefaultTableModel tableModel;
    
    public UsersPanel(MainFrame mainFrame) {
        this.mainFrame = mainFrame;
        this.userDAO = new UserDAO();
        
        setLayout(new BorderLayout());
        setBackground(new Color(248, 250, 252));
        setBorder(new EmptyBorder(30, 30, 30, 30));
        
        initComponents();
    }
    
    private void initComponents() {
        JLabel titleLabel = new JLabel("Users Management");
        titleLabel.setFont(new Font("Arial", Font.BOLD, 28));
        titleLabel.setForeground(new Color(31, 58, 95));
        
        JPanel topPanel = new JPanel(new BorderLayout());
        topPanel.setBackground(new Color(248, 250, 252));
        topPanel.add(titleLabel, BorderLayout.WEST);
        
        JButton refreshBtn = createButton("Refresh", new Color(139, 92, 246));
        refreshBtn.addActionListener(e -> refresh());
        
        JButton activateBtn = createButton("Activate", new Color(16, 185, 129));
        activateBtn.addActionListener(e -> setUserActive(true));
        
        JButton deactivateBtn = createButton("Deactivate", new Color(239, 68, 68));
        deactivateBtn.addActionListener(e -> setUserActive(false));
        
        JPanel btnPanel = new JPanel(new FlowLayout(FlowLayout.RIGHT, 10, 0));
        btnPanel.setBackground(new Color(248, 250, 252));
        btnPanel.add(refreshBtn);
        btnPanel.add(activateBtn);
        btnPanel.add(deactivateBtn);
        
        topPanel.add(btnPanel, BorderLayout.EAST);
        add(topPanel, BorderLayout.NORTH);
        
        String[] columns = {"ID", "Name", "Email", "Phone", "Role", "Active", "Verified", "Created"};
        tableModel = new DefaultTableModel(columns, 0) {
            @Override
            public boolean isCellEditable(int row, int column) {
                return false;
            }
        };
        
        table = new JTable(tableModel);
        table.setRowHeight(35);
        table.setFont(new Font("Arial", Font.PLAIN, 14));
        table.getTableHeader().setFont(new Font("Arial", Font.BOLD, 14));
        table.getTableHeader().setBackground(new Color(15, 59, 111));
        table.getTableHeader().setForeground(Color.WHITE);
        
        JScrollPane scrollPane = new JScrollPane(table);
        scrollPane.setBorder(BorderFactory.createLineBorder(new Color(226, 232, 240)));
        
        add(scrollPane, BorderLayout.CENTER);
    }
    
    private JButton createButton(String text, Color color) {
        JButton btn = new JButton(text);
        btn.setFont(new Font("Arial", Font.BOLD, 14));
        btn.setForeground(Color.WHITE);
        btn.setBackground(color);
        btn.setFocusPainted(false);
        btn.setBorderPainted(false);
        btn.setCursor(Cursor.getPredefinedCursor(Cursor.HAND_CURSOR));
        btn.setPreferredSize(new Dimension(130, 40));
        return btn;
    }
    
    public void refresh() {
        try {
            tableModel.setRowCount(0);
            List<User> users = userDAO.getAllUsers();
            
            for (User u : users) {
                String created = u.getCreatedAt() != null ? u.getCreatedAt().toString().substring(0, 10) : "N/A";
                
                tableModel.addRow(new Object[]{
                    u.getId(), u.getFullName(), u.getEmail(), u.getPhone(),
                    u.getRole(), u.isActive() ? "Yes" : "No",
                    u.isEmailVerified() ? "Yes" : "No", created
                });
            }
        } catch (Exception e) {
            e.printStackTrace();
            JOptionPane.showMessageDialog(mainFrame, "Error loading users: " + e.getMessage());
        }
    }
    
    private void setUserActive(boolean active) {
        int selectedRow = table.getSelectedRow();
        if (selectedRow < 0) {
            JOptionPane.showMessageDialog(mainFrame, "Please select a user");
            return;
        }
        
        int userId = (Integer) tableModel.getValueAt(selectedRow, 0);
        User user = userDAO.getUserById(userId);
        
        if (user != null) {
            user.setActive(active);
            if (userDAO.updateUser(user)) {
                JOptionPane.showMessageDialog(mainFrame, "User " + (active ? "activated" : "deactivated"));
                refresh();
            }
        }
    }
}