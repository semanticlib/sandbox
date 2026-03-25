/**
 * Virtualization support detection
 * Checks if the system supports hardware virtualization for VMs
 */

let vmSupportInfo = null;

/**
 * Check VM support from API and cache the result
 */
export async function checkVMSupport() {
    if (vmSupportInfo !== null) {
        return vmSupportInfo;
    }

    try {
        const response = await fetch('/api/vm-support');
        const data = await response.json();
        vmSupportInfo = data;
        return data;
    } catch (error) {
        console.error('Failed to check VM support:', error);
        // Default to assuming VMs are supported if check fails
        return {
            vm_supported: true,
            container_supported: true,
            recommendation: ''
        };
    }
}

/**
 * Disable VM options in the UI if virtualization is not supported
 */
export function disableVMOptionsIfUnsupported() {
    checkVMSupport().then(info => {
        if (!info.vm_supported) {
            // Disable VM option in instance type dropdown
            const instanceTypeSelect = document.getElementById('instance_type');
            if (instanceTypeSelect) {
                const vmOption = instanceTypeSelect.querySelector('option[value="virtual-machine"]');
                if (vmOption) {
                    vmOption.disabled = true;
                    vmOption.textContent = 'VM (Not available on this system)';
                    
                    // If VM is currently selected, switch to container
                    if (instanceTypeSelect.value === 'virtual-machine') {
                        instanceTypeSelect.value = 'container';
                    }
                }
            }

            // Show warning message in create form
            const createForm = document.getElementById('create-form');
            if (createForm) {
                const existingWarning = createForm.querySelector('.vm-not-supported-warning');
                if (!existingWarning) {
                    const warningDiv = document.createElement('div');
                    warningDiv.className = 'alert alert-warning vm-not-supported-warning';
                    warningDiv.innerHTML = `
                        <i class="bi bi-exclamation-triangle"></i>
                        <strong>Virtual machines not available:</strong> ${info.recommendation}
                    `;
                    createForm.insertBefore(warningDiv, createForm.firstChild);
                }
            }

            // Disable VM Settings tab
            const vmSettingsTab = document.getElementById('vm-settings-tab');
            const vmSettingsPane = document.getElementById('vm-settings');
            if (vmSettingsTab) {
                vmSettingsTab.classList.add('disabled');
                vmSettingsTab.style.pointerEvents = 'none';
                vmSettingsTab.style.opacity = '0.5';
                vmSettingsTab.title = 'Virtual machines are not supported on this system';
                
                // Add tooltip explanation
                const tooltip = document.createElement('span');
                tooltip.className = 'badge bg-warning ms-2';
                tooltip.textContent = 'Not Available';
                vmSettingsTab.appendChild(tooltip);
            }
            if (vmSettingsPane) {
                vmSettingsPane.classList.add('disabled');
            }

            // Auto-switch to Container Settings tab if on VM Settings
            const containerSettingsTab = document.getElementById('container-settings-tab');
            if (containerSettingsTab && vmSettingsTab) {
                const activeTab = document.querySelector('.nav-link.active');
                if (activeTab === vmSettingsTab) {
                    containerSettingsTab.click();
                }
            }

            console.log('VM support disabled:', info);
        }
    });
}

/**
 * Get cached VM support info
 */
export function getVMSupportInfo() {
    return vmSupportInfo;
}
