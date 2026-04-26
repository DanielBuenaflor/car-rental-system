package com.carrental.admin.ui;

import com.carrental.admin.dao.TestimonialDAO;
import com.carrental.admin.model.Testimonial;
import javax.swing.*;
import javax.swing.border.EmptyBorder;
import javax.swing.table.DefaultTableModel;
import java.awt.*;
import java.util.List;

public class TestimonialsPanel extends JPanel {
    private MainFrame mainFrame;
    private TestimonialDAO testimonialDAO;
    private JTable table;
    private DefaultTableModel tableModel;
    
    public TestimonialsPanel(MainFrame mainFrame) {
        this.mainFrame = mainFrame;
        this.testimonialDAO = new TestimonialDAO();
        
        setLayout(new BorderLayout());
        setBackground(new Color(248, 250, 252));
        setBorder(new EmptyBorder(30, 30, 30, 30));
        
        initComponents();
    }
    
    private void initComponents() {
        JLabel titleLabel = new JLabel("Testimonials / Reviews");
        titleLabel.setFont(new Font("Arial", Font.BOLD, 28));
        titleLabel.setForeground(new Color(31, 58, 95));
        
        JPanel topPanel = new JPanel(new BorderLayout());
        topPanel.setBackground(new Color(248, 250, 252));
        topPanel.add(titleLabel, BorderLayout.WEST);
        
        JButton refreshBtn = createButton("Refresh", new Color(139, 92, 246));
        refreshBtn.addActionListener(e -> refresh());
        
        JButton approveBtn = createButton("Approve", new Color(16, 185, 129));
        approveBtn.addActionListener(e -> updateStatus("approved"));
        
        JButton rejectBtn = createButton("Reject", new Color(239, 68, 68));
        rejectBtn.addActionListener(e -> updateStatus("rejected"));
        
        JPanel btnPanel = new JPanel(new FlowLayout(FlowLayout.RIGHT, 10, 0));
        btnPanel.setBackground(new Color(248, 250, 252));
        btnPanel.add(refreshBtn);
        btnPanel.add(approveBtn);
        btnPanel.add(rejectBtn);
        
        topPanel.add(btnPanel, BorderLayout.EAST);
        add(topPanel, BorderLayout.NORTH);
        
        String[] columns = {"ID", "User", "Rating", "Comment", "Status", "Date"};
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
            List<Testimonial> list = testimonialDAO.getAllTestimonials();
            
            for (Testimonial t : list) {
                String date = t.getCreatedAt() != null ? t.getCreatedAt().toString().substring(0, 10) : "N/A";
                tableModel.addRow(new Object[]{
                    t.getId(), t.getUserName(), 
                    t.getRating() + "/5", 
                    t.getComment() != null && t.getComment().length() > 50 ? 
                        t.getComment().substring(0, 50) + "..." : t.getComment(),
                    t.getStatus(), date
                });
            }
        } catch (Exception e) {
            e.printStackTrace();
            JOptionPane.showMessageDialog(mainFrame, "Error: " + e.getMessage());
        }
    }
    
    private void updateStatus(String status) {
        int selectedRow = table.getSelectedRow();
        if (selectedRow < 0) {
            JOptionPane.showMessageDialog(mainFrame, "Select a testimonial");
            return;
        }
        
        int id = (Integer) tableModel.getValueAt(selectedRow, 0);
        if (testimonialDAO.updateStatus(id, status)) {
            JOptionPane.showMessageDialog(mainFrame, "Testimonial " + status + "!");
            refresh();
        }
    }
}