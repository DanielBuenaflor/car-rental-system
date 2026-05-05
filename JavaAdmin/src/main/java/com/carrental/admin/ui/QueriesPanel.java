package com.carrental.admin.ui;

import com.carrental.admin.dao.ContactQueryDAO;
import com.carrental.admin.model.ContactQuery;
import javax.swing.*;
import javax.swing.border.EmptyBorder;
import javax.swing.table.DefaultTableModel;
import java.awt.*;
import java.util.List;

public class QueriesPanel extends JPanel {
    private MainFrame mainFrame;
    private ContactQueryDAO queryDAO;
    private JTable table;
    private DefaultTableModel tableModel;
    
    public QueriesPanel(MainFrame mainFrame) {
        this.mainFrame = mainFrame;
        this.queryDAO = new ContactQueryDAO();
        
        setLayout(new BorderLayout());
        setBackground(new Color(248, 250, 252));
        setBorder(new EmptyBorder(30, 30, 30, 30));
        
        initComponents();
    }
    
    private void initComponents() {
        JLabel titleLabel = new JLabel("Contact Queries");
        titleLabel.setFont(new Font("Arial", Font.BOLD, 28));
        titleLabel.setForeground(new Color(31, 58, 95));
        
        JPanel topPanel = new JPanel(new BorderLayout());
        topPanel.setBackground(new Color(248, 250, 252));
        topPanel.add(titleLabel, BorderLayout.WEST);
        
        JButton refreshBtn = createButton("Refresh", new Color(139, 92, 246));
        refreshBtn.addActionListener(e -> refresh());
        
        JButton replyBtn = createButton("Reply", new Color(16, 185, 129));
        replyBtn.addActionListener(e -> showReplyDialog());
        
        JPanel btnPanel = new JPanel(new FlowLayout(FlowLayout.RIGHT, 10, 0));
        btnPanel.setBackground(new Color(248, 250, 252));
        btnPanel.add(refreshBtn);
        btnPanel.add(replyBtn);
        
        topPanel.add(btnPanel, BorderLayout.EAST);
        add(topPanel, BorderLayout.NORTH);
        
        String[] columns = {"ID", "Name", "Email", "Subject", "Message", "Status", "Date"};
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
        btn.setPreferredSize(new Dimension(120, 40));
        return btn;
    }
    
    public void refresh() {
        try {
            tableModel.setRowCount(0);
            List<ContactQuery> list = queryDAO.getAllQueries();
            
            for (ContactQuery q : list) {
                String date = q.getCreatedAt() != null ? q.getCreatedAt().toString().substring(0, 10) : "N/A";
                tableModel.addRow(new Object[]{
                    q.getId(), q.getName(), q.getEmail(), q.getSubject(),
                    q.getMessage() != null && q.getMessage().length() > 40 ? 
                        q.getMessage().substring(0, 40) + "..." : q.getMessage(),
                    q.getStatus(), date
                });
            }
        } catch (Exception e) {
            e.printStackTrace();
            JOptionPane.showMessageDialog(mainFrame, "Error: " + e.getMessage());
        }
    }
    
    private void showReplyDialog() {
        int selectedRow = table.getSelectedRow();
        if (selectedRow < 0) {
            JOptionPane.showMessageDialog(mainFrame, "Select a query");
            return;
        }
        
        int id = (Integer) tableModel.getValueAt(selectedRow, 0);
        
        JDialog dialog = new JDialog(mainFrame, "Reply to Query", true);
        dialog.setSize(500, 300);
        dialog.setLocationRelativeTo(mainFrame);
        
        JPanel formPanel = new JPanel(new BorderLayout(10, 10));
        formPanel.setBorder(new EmptyBorder(20, 20, 20, 20));
        
        formPanel.add(new JLabel("Enter your reply:"), BorderLayout.NORTH);
        
        JTextArea replyArea = new JTextArea(10, 40);
        replyArea.setLineWrap(true);
        replyArea.setWrapStyleWord(true);
        formPanel.add(new JScrollPane(replyArea), BorderLayout.CENTER);
        
        JButton sendBtn = createButton("Send Reply", new Color(16, 185, 129));
        sendBtn.addActionListener(e -> {
            String reply = replyArea.getText();
            if (reply != null && !reply.trim().isEmpty()) {
                if (queryDAO.replyToQuery(id, reply)) {
                    JOptionPane.showMessageDialog(dialog, "Reply sent!");
                    dialog.dispose();
                    refresh();
                }
            }
        });
        
        JButton cancelBtn = createButton("Cancel", new Color(107, 114, 128));
        cancelBtn.addActionListener(e -> dialog.dispose());
        
        JPanel btnPanel = new JPanel(new FlowLayout(FlowLayout.RIGHT));
        btnPanel.add(sendBtn);
        btnPanel.add(cancelBtn);
        
        formPanel.add(btnPanel, BorderLayout.SOUTH);
        
        dialog.add(formPanel, BorderLayout.CENTER);
        dialog.setVisible(true);
    }
}