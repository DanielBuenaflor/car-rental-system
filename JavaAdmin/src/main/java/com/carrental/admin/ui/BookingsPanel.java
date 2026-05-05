package com.carrental.admin.ui;

import com.carrental.admin.dao.BookingDAO;
import com.carrental.admin.model.Booking;
import javax.swing.*;
import javax.swing.border.EmptyBorder;
import javax.swing.table.DefaultTableModel;
import java.awt.*;
import java.util.List;

public class BookingsPanel extends JPanel {
    private MainFrame mainFrame;
    private BookingDAO bookingDAO;
    private JTable table;
    private DefaultTableModel tableModel;
    
    public BookingsPanel(MainFrame mainFrame) {
        this.mainFrame = mainFrame;
        this.bookingDAO = new BookingDAO();
        
        setLayout(new BorderLayout());
        setBackground(new Color(248, 250, 252));
        setBorder(new EmptyBorder(30, 30, 30, 30));
        
        initComponents();
    }
    
    private void initComponents() {
        JLabel titleLabel = new JLabel("Bookings Management");
        titleLabel.setFont(new Font("Arial", Font.BOLD, 28));
        titleLabel.setForeground(new Color(31, 58, 95));
        
        JPanel topPanel = new JPanel(new BorderLayout());
        topPanel.setBackground(new Color(248, 250, 252));
        topPanel.add(titleLabel, BorderLayout.WEST);
        
        JButton refreshBtn = createButton("Refresh", new Color(139, 92, 246));
        refreshBtn.addActionListener(e -> refresh());
        
        JButton confirmBtn = createButton("Confirm", new Color(16, 185, 129));
        confirmBtn.addActionListener(e -> updateStatus("confirmed"));
        
        JButton completeBtn = createButton("Complete", new Color(59, 130, 246));
        completeBtn.addActionListener(e -> updateStatus("completed"));
        
        JButton cancelBtn = createButton("Cancel", new Color(239, 68, 68));
        cancelBtn.addActionListener(e -> cancelBooking());
        
        JPanel btnPanel = new JPanel(new FlowLayout(FlowLayout.RIGHT, 10, 0));
        btnPanel.setBackground(new Color(248, 250, 252));
        btnPanel.add(refreshBtn);
        btnPanel.add(confirmBtn);
        btnPanel.add(completeBtn);
        btnPanel.add(cancelBtn);
        
        topPanel.add(btnPanel, BorderLayout.EAST);
        add(topPanel, BorderLayout.NORTH);
        
        String[] columns = {"ID", "Reference", "Customer", "Vehicle", "Start Date", "End Date", "Total", "Status"};
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
            List<Booking> bookings = bookingDAO.getAllBookings();
            
            for (Booking b : bookings) {
                String startDate = b.getStartDate() != null ? b.getStartDate().toString().substring(0, 16) : "N/A";
                String endDate = b.getEndDate() != null ? b.getEndDate().toString().substring(0, 16) : "N/A";
                
                tableModel.addRow(new Object[]{
                    b.getId(), b.getBookingReference(), b.getUserName(), 
                    b.getVehicleBrand() + " " + b.getVehicleModel(),
                    startDate, endDate,
                    "₱" + b.getTotalAmount(), b.getStatus()
                });
            }
        } catch (Exception e) {
            e.printStackTrace();
            JOptionPane.showMessageDialog(mainFrame, "Error loading bookings: " + e.getMessage());
        }
    }
    
    private void updateStatus(String status) {
        int selectedRow = table.getSelectedRow();
        if (selectedRow < 0) {
            JOptionPane.showMessageDialog(mainFrame, "Please select a booking");
            return;
        }
        
        int bookingId = (Integer) tableModel.getValueAt(selectedRow, 0);
        if (bookingDAO.updateBookingStatus(bookingId, status)) {
            JOptionPane.showMessageDialog(mainFrame, "Booking status updated to " + status);
            refresh();
        }
    }
    
    private void cancelBooking() {
        int selectedRow = table.getSelectedRow();
        if (selectedRow < 0) {
            JOptionPane.showMessageDialog(mainFrame, "Please select a booking");
            return;
        }
        
        String reason = JOptionPane.showInputDialog(mainFrame, "Enter cancellation reason:");
        if (reason != null && !reason.trim().isEmpty()) {
            int bookingId = (Integer) tableModel.getValueAt(selectedRow, 0);
            if (bookingDAO.cancelBooking(bookingId, reason)) {
                JOptionPane.showMessageDialog(mainFrame, "Booking cancelled");
                refresh();
            }
        }
    }
}