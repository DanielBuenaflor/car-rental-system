package com.carrental.admin.ui;

import com.carrental.admin.dao.BrandDAO;
import com.carrental.admin.model.Brand;
import javax.swing.*;
import javax.swing.border.EmptyBorder;
import javax.swing.table.DefaultTableModel;
import java.awt.*;
import java.util.List;

public class BrandsPanel extends JPanel {
    private MainFrame mainFrame;
    private BrandDAO brandDAO;
    private JTable table;
    private DefaultTableModel tableModel;
    
    public BrandsPanel(MainFrame mainFrame) {
        this.mainFrame = mainFrame;
        this.brandDAO = new BrandDAO();
        
        setLayout(new BorderLayout());
        setBackground(new Color(248, 250, 252));
        setBorder(new EmptyBorder(30, 30, 30, 30));
        
        initComponents();
    }
    
    private void initComponents() {
        JLabel titleLabel = new JLabel("Vehicle Brands");
        titleLabel.setFont(new Font("Arial", Font.BOLD, 28));
        titleLabel.setForeground(new Color(31, 58, 95));
        
        JPanel topPanel = new JPanel(new BorderLayout());
        topPanel.setBackground(new Color(248, 250, 252));
        topPanel.add(titleLabel, BorderLayout.WEST);
        
        JButton addBtn = createButton("Add Brand", new Color(16, 185, 129));
        addBtn.addActionListener(e -> showAddDialog());
        
        JButton deleteBtn = createButton("Delete", new Color(239, 68, 68));
        deleteBtn.addActionListener(e -> deleteBrand());
        
        JButton refreshBtn = createButton("Refresh", new Color(139, 92, 246));
        refreshBtn.addActionListener(e -> refresh());
        
        JPanel btnPanel = new JPanel(new FlowLayout(FlowLayout.RIGHT, 10, 0));
        btnPanel.setBackground(new Color(248, 250, 252));
        btnPanel.add(addBtn);
        btnPanel.add(deleteBtn);
        btnPanel.add(refreshBtn);
        
        topPanel.add(btnPanel, BorderLayout.EAST);
        add(topPanel, BorderLayout.NORTH);
        
        String[] columns = {"ID", "Name", "Description", "Founded", "Country", "Created"};
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
            List<Brand> brands = brandDAO.getAllBrands();
            
            for (Brand b : brands) {
                String created = b.getCreatedAt() != null ? b.getCreatedAt().toString().substring(0, 10) : "N/A";
                tableModel.addRow(new Object[]{
                    b.getId(), b.getName(), b.getDescription(),
                    b.getFoundedYear() != null ? b.getFoundedYear() : "N/A",
                    b.getCountryOfOrigin() != null ? b.getCountryOfOrigin() : "N/A", created
                });
            }
        } catch (Exception e) {
            e.printStackTrace();
            JOptionPane.showMessageDialog(mainFrame, "Error: " + e.getMessage());
        }
    }
    
    private void showAddDialog() {
        JDialog dialog = new JDialog(mainFrame, "Add Brand", true);
        dialog.setSize(400, 300);
        dialog.setLocationRelativeTo(mainFrame);
        
        JPanel formPanel = new JPanel(new GridLayout(0, 2, 10, 10));
        formPanel.setBorder(new EmptyBorder(20, 20, 20, 20));
        
        JTextField nameField = new JTextField();
        JTextField descField = new JTextField();
        JSpinner yearSpinner = new JSpinner(new SpinnerNumberModel(2020, 1900, 2030, 1));
        JTextField countryField = new JTextField();
        
        formPanel.add(new JLabel("Brand Name:"));
        formPanel.add(nameField);
        formPanel.add(new JLabel("Description:"));
        formPanel.add(descField);
        formPanel.add(new JLabel("Founded Year:"));
        formPanel.add(yearSpinner);
        formPanel.add(new JLabel("Country:"));
        formPanel.add(countryField);
        
        JButton saveBtn = createButton("Save", new Color(16, 185, 129));
        saveBtn.addActionListener(e -> {
            try {
                Brand b = new Brand();
                b.setName(nameField.getText());
                b.setDescription(descField.getText());
                b.setFoundedYear((Integer) yearSpinner.getValue());
                b.setCountryOfOrigin(countryField.getText());
                
                if (brandDAO.insertBrand(b)) {
                    JOptionPane.showMessageDialog(dialog, "Brand added!");
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
    
    private void deleteBrand() {
        int selectedRow = table.getSelectedRow();
        if (selectedRow < 0) {
            JOptionPane.showMessageDialog(mainFrame, "Select a brand");
            return;
        }
        
        int confirm = JOptionPane.showConfirmDialog(mainFrame, "Delete brand?", "Confirm", JOptionPane.YES_NO_OPTION);
        if (confirm == JOptionPane.YES_OPTION) {
            int brandId = (Integer) tableModel.getValueAt(selectedRow, 0);
            if (brandDAO.deleteBrand(brandId)) {
                JOptionPane.showMessageDialog(mainFrame, "Brand deleted!");
                refresh();
            }
        }
    }
}