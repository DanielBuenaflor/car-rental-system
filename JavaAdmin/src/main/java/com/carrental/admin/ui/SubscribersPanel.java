package com.carrental.admin.ui;

import com.carrental.admin.dao.SubscriberDAO;
import com.carrental.admin.model.Subscriber;
import javax.swing.*;
import javax.swing.border.EmptyBorder;
import javax.swing.table.DefaultTableModel;
import java.awt.*;
import java.util.List;

public class SubscribersPanel extends JPanel {
    private MainFrame mainFrame;
    private SubscriberDAO subscriberDAO;
    private JTable table;
    private DefaultTableModel tableModel;
    
    public SubscribersPanel(MainFrame mainFrame) {
        this.mainFrame = mainFrame;
        this.subscriberDAO = new SubscriberDAO();
        
        setLayout(new BorderLayout());
        setBackground(new Color(248, 250, 252));
        setBorder(new EmptyBorder(30, 30, 30, 30));
        
        initComponents();
    }
    
    private void initComponents() {
        JLabel titleLabel = new JLabel("Newsletter Subscribers");
        titleLabel.setFont(new Font("Arial", Font.BOLD, 28));
        titleLabel.setForeground(new Color(31, 58, 95));
        
        JPanel topPanel = new JPanel(new BorderLayout());
        topPanel.setBackground(new Color(248, 250, 252));
        topPanel.add(titleLabel, BorderLayout.WEST);
        
        JButton refreshBtn = createButton("Refresh", new Color(139, 92, 246));
        refreshBtn.addActionListener(e -> refresh());
        
        JButton unsubscribeBtn = createButton("Unsubscribe", new Color(239, 68, 68));
        unsubscribeBtn.addActionListener(e -> updateSubscription(false));
        
        JButton subscribeBtn = createButton("Subscribe", new Color(16, 185, 129));
        subscribeBtn.addActionListener(e -> updateSubscription(true));
        
        JPanel btnPanel = new JPanel(new FlowLayout(FlowLayout.RIGHT, 10, 0));
        btnPanel.setBackground(new Color(248, 250, 252));
        btnPanel.add(refreshBtn);
        btnPanel.add(subscribeBtn);
        btnPanel.add(unsubscribeBtn);
        
        topPanel.add(btnPanel, BorderLayout.EAST);
        add(topPanel, BorderLayout.NORTH);
        
        String[] columns = {"ID", "Email", "Active", "Subscribed Date"};
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
            List<Subscriber> list = subscriberDAO.getAllSubscribers();
            
            for (Subscriber s : list) {
                String date = s.getSubscribedAt() != null ? s.getSubscribedAt().toString().substring(0, 10) : "N/A";
                tableModel.addRow(new Object[]{
                    s.getId(), s.getEmail(), 
                    s.isActive() ? "Yes" : "No", date
                });
            }
        } catch (Exception e) {
            e.printStackTrace();
            JOptionPane.showMessageDialog(mainFrame, "Error: " + e.getMessage());
        }
    }
    
    private void updateSubscription(boolean active) {
        int selectedRow = table.getSelectedRow();
        if (selectedRow < 0) {
            JOptionPane.showMessageDialog(mainFrame, "Select a subscriber");
            return;
        }
        
        int id = (Integer) tableModel.getValueAt(selectedRow, 0);
        if (subscriberDAO.updateStatus(id, active)) {
            JOptionPane.showMessageDialog(mainFrame, "Subscriber " + (active ? "subscribed" : "unsubscribed"));
            refresh();
        }
    }
}