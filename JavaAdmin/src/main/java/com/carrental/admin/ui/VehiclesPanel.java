package com.carrental.admin.ui;

import com.carrental.admin.dao.VehicleDAO;
import com.carrental.admin.dao.BrandDAO;
import com.carrental.admin.model.Vehicle;
import com.carrental.admin.model.Brand;
import javax.swing.*;
import javax.swing.border.EmptyBorder;
import javax.swing.table.DefaultTableModel;
import java.awt.*;
import java.util.List;

public class VehiclesPanel extends JPanel {
    private MainFrame mainFrame;
    private VehicleDAO vehicleDAO;
    private BrandDAO brandDAO;
    private JTable table;
    private DefaultTableModel tableModel;
    
    public VehiclesPanel(MainFrame mainFrame) {
        this.mainFrame = mainFrame;
        this.vehicleDAO = new VehicleDAO();
        this.brandDAO = new BrandDAO();
        
        setLayout(new BorderLayout());
        setBackground(new Color(248, 250, 252));
        setBorder(new EmptyBorder(30, 30, 30, 30));
        
        initComponents();
    }
    
    private void initComponents() {
        JLabel titleLabel = new JLabel("Vehicles Management");
        titleLabel.setFont(new Font("Arial", Font.BOLD, 28));
        titleLabel.setForeground(new Color(31, 58, 95));
        
        JPanel topPanel = new JPanel(new BorderLayout());
        topPanel.setBackground(new Color(248, 250, 252));
        topPanel.add(titleLabel, BorderLayout.WEST);
        
        JButton addBtn = createButton("Add Vehicle", new Color(16, 185, 129));
        addBtn.addActionListener(e -> showAddDialog());
        
        JButton editBtn = createButton("Edit", new Color(59, 130, 246));
        editBtn.addActionListener(e -> showEditDialog());
        
        JButton deleteBtn = createButton("Delete", new Color(239, 68, 68));
        deleteBtn.addActionListener(e -> deleteVehicle());
        
        JButton refreshBtn = createButton("Refresh", new Color(139, 92, 246));
        refreshBtn.addActionListener(e -> refresh());
        
        JPanel btnPanel = new JPanel(new FlowLayout(FlowLayout.RIGHT, 10, 0));
        btnPanel.setBackground(new Color(248, 250, 252));
        btnPanel.add(addBtn);
        btnPanel.add(editBtn);
        btnPanel.add(deleteBtn);
        btnPanel.add(refreshBtn);
        
        topPanel.add(btnPanel, BorderLayout.EAST);
        
        add(topPanel, BorderLayout.NORTH);
        
        String[] columns = {"ID", "Brand", "Model", "Year", "License Plate", "Transmission", "Fuel", "Daily Rate", "Status"};
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
            List<Vehicle> vehicles = vehicleDAO.getAllVehicles();
            
            for (Vehicle v : vehicles) {
                tableModel.addRow(new Object[]{
                    v.getId(), v.getBrandName(), v.getModel(), v.getYear(),
                    v.getLicensePlate(), v.getTransmission(), v.getFuelType(),
                    "₱" + v.getDailyRate(), v.getStatus()
                });
            }
        } catch (Exception e) {
            e.printStackTrace();
            JOptionPane.showMessageDialog(mainFrame, "Error loading vehicles: " + e.getMessage());
        }
    }
    
    private void showAddDialog() {
        JDialog dialog = new JDialog(mainFrame, "Add Vehicle", true);
        dialog.setSize(600, 500);
        dialog.setLocationRelativeTo(mainFrame);
        
        JPanel formPanel = new JPanel(new GridLayout(0, 2, 10, 10));
        formPanel.setBorder(new EmptyBorder(20, 20, 20, 20));
        
        JComboBox<String> brandCombo = new JComboBox<>();
        for (Brand b : brandDAO.getAllBrands()) {
            brandCombo.addItem(b.getId() + "-" + b.getName());
        }
        
        JTextField modelField = new JTextField();
        JSpinner yearSpinner = new JSpinner(new SpinnerNumberModel(2026, 2000, 2030, 1));
        JTextField plateField = new JTextField();
        JTextField colorField = new JTextField();
        JComboBox<String> transCombo = new JComboBox<>(new String[]{"manual", "automatic"});
        JComboBox<String> fuelCombo = new JComboBox<>(new String[]{"petrol", "diesel", "electric", "hybrid"});
        JSpinner capacitySpinner = new JSpinner(new SpinnerNumberModel(5, 2, 15, 1));
        JSpinner dailyRateSpinner = new JSpinner(new SpinnerNumberModel(1000.0, 0.0, 50000.0, 100.0));
        JSpinner weeklyRateSpinner = new JSpinner(new SpinnerNumberModel(5000.0, 0.0, 200000.0, 500.0));
        JSpinner monthlyRateSpinner = new JSpinner(new SpinnerNumberModel(15000.0, 0.0, 500000.0, 1000.0));
        JSpinner depositSpinner = new JSpinner(new SpinnerNumberModel(5000.0, 0.0, 100000.0, 500.0));
        JComboBox<String> statusCombo = new JComboBox<>(new String[]{"available", "rented", "maintenance", "reserved", "unavailable"});
        
        formPanel.add(new JLabel("Brand:"));
        formPanel.add(brandCombo);
        formPanel.add(new JLabel("Model:"));
        formPanel.add(modelField);
        formPanel.add(new JLabel("Year:"));
        formPanel.add(yearSpinner);
        formPanel.add(new JLabel("License Plate:"));
        formPanel.add(plateField);
        formPanel.add(new JLabel("Color:"));
        formPanel.add(colorField);
        formPanel.add(new JLabel("Transmission:"));
        formPanel.add(transCombo);
        formPanel.add(new JLabel("Fuel Type:"));
        formPanel.add(fuelCombo);
        formPanel.add(new JLabel("Seating Capacity:"));
        formPanel.add(capacitySpinner);
        formPanel.add(new JLabel("Daily Rate:"));
        formPanel.add(dailyRateSpinner);
        formPanel.add(new JLabel("Weekly Rate:"));
        formPanel.add(weeklyRateSpinner);
        formPanel.add(new JLabel("Monthly Rate:"));
        formPanel.add(monthlyRateSpinner);
        formPanel.add(new JLabel("Security Deposit:"));
        formPanel.add(depositSpinner);
        formPanel.add(new JLabel("Status:"));
        formPanel.add(statusCombo);
        
        JButton saveBtn = createButton("Save", new Color(16, 185, 129));
        saveBtn.addActionListener(e -> {
            try {
                Vehicle v = new Vehicle();
                String brandItem = (String) brandCombo.getSelectedItem();
                v.setBrandId(Integer.parseInt(brandItem.split("-")[0]));
                v.setModel(modelField.getText());
                v.setYear((Integer) yearSpinner.getValue());
                v.setLicensePlate(plateField.getText());
                v.setColor(colorField.getText());
                v.setTransmission((String) transCombo.getSelectedItem());
                v.setFuelType((String) fuelCombo.getSelectedItem());
                v.setSeatingCapacity((Integer) capacitySpinner.getValue());
                v.setDailyRate((java.math.BigDecimal) dailyRateSpinner.getValue());
                v.setWeeklyRate((java.math.BigDecimal) weeklyRateSpinner.getValue());
                v.setMonthlyRate((java.math.BigDecimal) monthlyRateSpinner.getValue());
                v.setSecurityDeposit((java.math.BigDecimal) depositSpinner.getValue());
                v.setStatus((String) statusCombo.getSelectedItem());
                v.setMileageLimitKm(200);
                v.setExcessKmCharge(new java.math.BigDecimal("10.00"));
                
                if (vehicleDAO.insertVehicle(v)) {
                    JOptionPane.showMessageDialog(dialog, "Vehicle added successfully!");
                    dialog.dispose();
                    refresh();
                }
            } catch (Exception ex) {
                JOptionPane.showMessageDialog(dialog, "Error: " + ex.getMessage());
            }
        });
        
        JButton cancelBtn = createButton("Cancel", new Color(107, 114, 128));
        cancelBtn.addActionListener(e -> dialog.dispose());
        
        JPanel btnPanel = new JPanel(new FlowLayout(FlowLayout.RIGHT));
        btnPanel.add(saveBtn);
        btnPanel.add(cancelBtn);
        
        dialog.add(formPanel, BorderLayout.CENTER);
        dialog.add(btnPanel, BorderLayout.SOUTH);
        dialog.setVisible(true);
    }
    
    private void showEditDialog() {
        int selectedRow = table.getSelectedRow();
        if (selectedRow < 0) {
            JOptionPane.showMessageDialog(mainFrame, "Please select a vehicle to edit");
            return;
        }
        
        int vehicleId = (Integer) tableModel.getValueAt(selectedRow, 0);
        Vehicle vehicle = vehicleDAO.getVehicleById(vehicleId);
        
        if (vehicle == null) {
            JOptionPane.showMessageDialog(mainFrame, "Vehicle not found");
            return;
        }
        
        JDialog dialog = new JDialog(mainFrame, "Edit Vehicle", true);
        dialog.setSize(600, 500);
        dialog.setLocationRelativeTo(mainFrame);
        
        JPanel formPanel = new JPanel(new GridLayout(0, 2, 10, 10));
        formPanel.setBorder(new EmptyBorder(20, 20, 20, 20));
        
        JComboBox<String> brandCombo = new JComboBox<>();
        for (Brand b : brandDAO.getAllBrands()) {
            brandCombo.addItem(b.getId() + "-" + b.getName());
            if (b.getId() == vehicle.getBrandId()) {
                brandCombo.setSelectedItem(b.getId() + "-" + b.getName());
            }
        }
        
        formPanel.add(new JLabel("Brand:"));
        formPanel.add(brandCombo);
        
        JTextField modelField = new JTextField(vehicle.getModel());
        formPanel.add(new JLabel("Model:"));
        formPanel.add(modelField);
        
        JSpinner yearSpinner = new JSpinner(new SpinnerNumberModel(vehicle.getYear(), 2000, 2030, 1));
        formPanel.add(new JLabel("Year:"));
        formPanel.add(yearSpinner);
        
        JTextField plateField = new JTextField(vehicle.getLicensePlate());
        formPanel.add(new JLabel("License Plate:"));
        formPanel.add(plateField);
        
        JTextField colorField = new JTextField(vehicle.getColor());
        formPanel.add(new JLabel("Color:"));
        formPanel.add(colorField);
        
        JComboBox<String> transCombo = new JComboBox<>(new String[]{"manual", "automatic"});
        transCombo.setSelectedItem(vehicle.getTransmission());
        formPanel.add(new JLabel("Transmission:"));
        formPanel.add(transCombo);
        
        JComboBox<String> statusCombo = new JComboBox<>(new String[]{"available", "rented", "maintenance", "reserved", "unavailable"});
        statusCombo.setSelectedItem(vehicle.getStatus());
        formPanel.add(new JLabel("Status:"));
        formPanel.add(statusCombo);
        
        JButton saveBtn = createButton("Save", new Color(16, 185, 129));
        saveBtn.addActionListener(e -> {
            try {
                vehicle.setBrandId(Integer.parseInt(((String) brandCombo.getSelectedItem()).split("-")[0]));
                vehicle.setModel(modelField.getText());
                vehicle.setYear((Integer) yearSpinner.getValue());
                vehicle.setLicensePlate(plateField.getText());
                vehicle.setColor(colorField.getText());
                vehicle.setTransmission((String) transCombo.getSelectedItem());
                vehicle.setStatus((String) statusCombo.getSelectedItem());
                
                if (vehicleDAO.updateVehicle(vehicle)) {
                    JOptionPane.showMessageDialog(dialog, "Vehicle updated successfully!");
                    dialog.dispose();
                    refresh();
                }
            } catch (Exception ex) {
                JOptionPane.showMessageDialog(dialog, "Error: " + ex.getMessage());
            }
        });
        
        JButton cancelBtn = createButton("Cancel", new Color(107, 114, 128));
        cancelBtn.addActionListener(e -> dialog.dispose());
        
        JPanel btnPanel = new JPanel(new FlowLayout(FlowLayout.RIGHT));
        btnPanel.add(saveBtn);
        btnPanel.add(cancelBtn);
        
        dialog.add(formPanel, BorderLayout.CENTER);
        dialog.add(btnPanel, BorderLayout.SOUTH);
        dialog.setVisible(true);
    }
    
    private void deleteVehicle() {
        int selectedRow = table.getSelectedRow();
        if (selectedRow < 0) {
            JOptionPane.showMessageDialog(mainFrame, "Please select a vehicle to delete");
            return;
        }
        
        int confirm = JOptionPane.showConfirmDialog(mainFrame, 
            "Are you sure you want to delete this vehicle?", "Confirm Delete",
            JOptionPane.YES_NO_OPTION);
        
        if (confirm == JOptionPane.YES_OPTION) {
            int vehicleId = (Integer) tableModel.getValueAt(selectedRow, 0);
            if (vehicleDAO.deleteVehicle(vehicleId)) {
                JOptionPane.showMessageDialog(mainFrame, "Vehicle deleted!");
                refresh();
            }
        }
    }
}