/**
 * Philippine Address Selector Utility (Local JSON Version)
 * Uses local data from /static/data/ph-locations.json
 */

const PhAddressSelector = {
    data: null,

    /**
     * Initialize cascading dropdowns
     * @param {Object} config - IDs of the select elements
     * @param {Object} initialValues - Values to set initially (optional)
     */
    init: async function(config, initialValues = {}) {
        const { regionId, provinceId, cityId, barangayId } = config;
        
        const regionSelect = document.getElementById(regionId);
        const provinceSelect = document.getElementById(provinceId);
        const citySelect = document.getElementById(cityId);
        const barangaySelect = document.getElementById(barangayId);

        if (!regionSelect) return;

        // Load Data if not already loaded
        if (!this.data) {
            await this.loadData(regionSelect);
        }

        if (!this.data) return;

        // Function to update hidden name fields
        const updateNameField = (selectEl, nameFieldId) => {
            const nameField = document.getElementById(nameFieldId);
            if (nameField && selectEl.selectedIndex > 0) {
                nameField.value = selectEl.options[selectEl.selectedIndex].text;
            } else if (nameField) {
                nameField.value = "";
            }
        };

        // Populate Regions
        this.populateRegions(regionSelect, initialValues.region);
        updateNameField(regionSelect, `${regionId}_name`);

        // Region Change Listener
        regionSelect.addEventListener('change', () => {
            const regionKey = regionSelect.value;
            updateNameField(regionSelect, `${regionId}_name`);
            
            this.resetSelect(provinceSelect, "Select Province");
            updateNameField(provinceSelect, `${provinceId}_name`);
            
            this.resetSelect(citySelect, "Select City/Municipality");
            updateNameField(citySelect, `${cityId}_name`);
            
            this.resetSelect(barangaySelect, "Select Barangay");
            updateNameField(barangaySelect, `${barangayId}_name`);

            if (regionKey) {
                this.populateProvinces(regionKey, provinceSelect);
                // Handle NCR/Regions without provinces
                const provinces = this.data[regionKey].province_list;
                if (Object.keys(provinces).length === 0 || (Object.keys(provinces).length === 1 && Object.keys(provinces)[0].includes("NCR"))) {
                     const firstProvKey = Object.keys(provinces)[0];
                     this.populateCities(regionKey, firstProvKey, citySelect);
                }
            }
        });

        // Province Change Listener
        if (provinceSelect) {
            provinceSelect.addEventListener('change', () => {
                const provinceKey = provinceSelect.value;
                updateNameField(provinceSelect, `${provinceId}_name`);
                
                this.resetSelect(citySelect, "Select City/Municipality");
                updateNameField(citySelect, `${cityId}_name`);
                
                this.resetSelect(barangaySelect, "Select Barangay");
                updateNameField(barangaySelect, `${barangayId}_name`);

                if (provinceKey) {
                    this.populateCities(regionSelect.value, provinceKey, citySelect);
                }
            });
        }

        // City Change Listener
        if (citySelect) {
            citySelect.addEventListener('change', () => {
                const cityKey = citySelect.value;
                updateNameField(citySelect, `${cityId}_name`);
                
                this.resetSelect(barangaySelect, "Select Barangay");
                updateNameField(barangaySelect, `${barangayId}_name`);

                if (cityKey) {
                    const provinceKey = provinceSelect.value || Object.keys(this.data[regionSelect.value].province_list)[0];
                    this.populateBarangays(regionSelect.value, provinceKey, cityKey, barangaySelect);
                }
            });
        }
        
        // Barangay Change Listener
        if (barangaySelect) {
            barangaySelect.addEventListener('change', () => {
                updateNameField(barangaySelect, `${barangayId}_name`);
            });
        }

        // Handle initial values for cascading
        if (initialValues.region) {
            const regionKey = Object.keys(this.data).find(k => this.data[k].region_name === initialValues.region);
            if (regionKey) {
                regionSelect.value = regionKey;
                updateNameField(regionSelect, `${regionId}_name`);
                
                this.populateProvinces(regionKey, provinceSelect);
                const provinces = this.data[regionKey].province_list;
                const provinceKey = Object.keys(provinces).find(k => k === initialValues.province) || Object.keys(provinces)[0];
                
                if (provinceKey) {
                    if (provinceSelect.disabled === false) provinceSelect.value = provinceKey;
                    updateNameField(provinceSelect, `${provinceId}_name`);
                    
                    this.populateCities(regionKey, provinceKey, citySelect);
                    const cities = provinces[provinceKey].municipality_list;
                    const cityKey = Object.keys(cities).find(k => k === initialValues.city);
                    
                    if (cityKey) {
                        citySelect.value = cityKey;
                        updateNameField(citySelect, `${cityId}_name`);
                        
                        this.populateBarangays(regionKey, provinceKey, cityKey, barangaySelect);
                        const barangays = cities[cityKey].barangay_list;
                        if (barangays.includes(initialValues.barangay)) {
                            barangaySelect.value = initialValues.barangay;
                            updateNameField(barangaySelect, `${barangayId}_name`);
                        }
                    }
                }
            }
        }
    },

    loadData: async function(selectEl) {
        selectEl.options[0].text = "Loading address data...";
        try {
            const response = await fetch('/static/data/ph-locations.json');
            if (!response.ok) throw new Error("Local data not found");
            this.data = await response.json();
            selectEl.options[0].text = "Select Region";
        } catch (error) {
            console.error("Error loading address data:", error);
            selectEl.options[0].text = "Error: Data file missing";
        }
    },

    populateRegions: function(selectEl, selectedName = null) {
        Object.keys(this.data).forEach(key => {
            const option = new Option(this.data[key].region_name, key);
            if (selectedName && this.data[key].region_name === selectedName) option.selected = true;
            selectEl.add(option);
        });
    },

    populateProvinces: function(regionKey, selectEl, selectedName = null) {
        const provinces = this.data[regionKey].province_list;
        const keys = Object.keys(provinces);
        
        if (keys.length === 0 || (keys.length === 1 && keys[0].includes("NCR"))) {
            selectEl.disabled = true;
            return;
        }

        selectEl.disabled = false;
        keys.sort().forEach(key => {
            const option = new Option(key, key);
            if (selectedName && key === selectedName) option.selected = true;
            selectEl.add(option);
        });
    },

    populateCities: function(regionKey, provinceKey, selectEl, selectedName = null) {
        const cities = this.data[regionKey].province_list[provinceKey].municipality_list;
        selectEl.disabled = false;
        Object.keys(cities).sort().forEach(key => {
            const option = new Option(key, key);
            if (selectedName && key === selectedName) option.selected = true;
            selectEl.add(option);
        });
    },

    populateBarangays: function(regionKey, provinceKey, cityKey, selectEl, selectedName = null) {
        const barangays = this.data[regionKey].province_list[provinceKey].municipality_list[cityKey].barangay_list;
        selectEl.disabled = false;
        barangays.sort().forEach(name => {
            const option = new Option(name, name);
            if (selectedName && name === selectedName) option.selected = true;
            selectEl.add(option);
        });
    },

    resetSelect: function(selectEl, placeholder) {
        if (!selectEl) return;
        selectEl.innerHTML = `<option value="">${placeholder}</option>`;
        selectEl.disabled = true;
    }
};
