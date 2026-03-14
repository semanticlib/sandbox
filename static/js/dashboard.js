// Instance creation with progress tracking
let createPollingInterval = null;

// Live search for instances table
function initLiveSearch() {
    const searchInput = document.getElementById('search-instances');
    const clearButton = document.getElementById('clear-search');
    
    if (!searchInput) return;
    
    // Show/hide clear button
    function updateClearButton() {
        clearButton.style.display = searchInput.value ? 'block' : 'none';
    }
    
    // Filter table rows
    function filterTable() {
        const searchTerm = searchInput.value.toLowerCase().trim();
        const rows = document.querySelectorAll('tbody tr');
        let visibleCount = 0;
        
        rows.forEach(row => {
            const nameCell = row.querySelector('td:nth-child(2)'); // Name is 2nd column (after checkbox)
            const ipCell = row.querySelector('td:nth-child(4)'); // IP is 4th column
            
            if (!nameCell) return;
            
            const name = nameCell.textContent.toLowerCase();
            const ip = ipCell ? ipCell.textContent.toLowerCase() : '';
            
            // Show row if search term matches name or IP
            if (searchTerm === '' || name.includes(searchTerm) || ip.includes(searchTerm)) {
                row.style.display = '';
                visibleCount++;
            } else {
                row.style.display = 'none';
            }
        });
        
        // Show "no results" message if needed
        let noResultsMsg = document.getElementById('no-results-message');
        if (visibleCount === 0 && searchTerm !== '') {
            if (!noResultsMsg) {
                noResultsMsg = document.createElement('div');
                noResultsMsg.id = 'no-results-message';
                noResultsMsg.className = 'alert alert-info mb-0';
                noResultsMsg.innerHTML = '<i class="bi bi-info-circle"></i> No instances matching your search';
                document.querySelector('.card-body').appendChild(noResultsMsg);
            }
            noResultsMsg.style.display = 'block';
        } else if (noResultsMsg) {
            noResultsMsg.style.display = 'none';
        }
        
        updateClearButton();
    }
    
    // Event listeners
    searchInput.addEventListener('input', filterTable);
    
    if (clearButton) {
        clearButton.addEventListener('click', () => {
            searchInput.value = '';
            filterTable();
            searchInput.focus();
        });
    }
    
    // Initial state
    updateClearButton();
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initLiveSearch();
    const form = document.getElementById('create-instance-form');
    if (form) {
        form.addEventListener('submit', async function(e) {
            e.preventDefault();

            const submitBtn = form.querySelector('button[type="submit"]');
            const progressContainer = document.getElementById('create-progress-container');
            const progressBar = document.getElementById('create-progress-bar');
            const progressText = document.getElementById('create-progress-text');
            const resultDiv = document.getElementById('create-result');

            // Get form values
            const formData = {
                name: form.instance_name.value.trim(),
                cpu: parseInt(form.instance_cpu.value),
                ram: parseInt(form.instance_ram.value),
                disk: parseInt(form.instance_disk.value),
                type: form.instance_type.value
            };

            // Disable form during creation
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Creating...';
            progressContainer.style.display = 'block';
            resultDiv.style.display = 'none';
            progressBar.style.width = '0%';
            progressBar.className = 'progress-bar progress-bar-striped progress-bar-animated';
            progressText.textContent = 'Initializing...';

            try {
                // Start instance creation
                const response = await fetch('/instances/create', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(formData)
                });

                const data = await response.json();

                if (!data.success) {
                    throw new Error(data.message || 'Failed to create instance');
                }

                const taskId = data.task_id;
                progressText.textContent = data.message || 'Creating instance...';

                // Start polling for progress
                createPollingInterval = setInterval(async () => {
                    try {
                        const statusResponse = await fetch(`/instances/create/status/${taskId}`);
                        const statusData = await statusResponse.json();

                        if (statusData.success) {
                            // Update progress
                            const progress = statusData.progress || 0;
                            progressBar.style.width = `${progress}%`;
                            progressText.textContent = statusData.message || `Creating instance... ${progress}%`;

                            if (statusData.done) {
                                // Creation complete
                                clearInterval(createPollingInterval);
                                progressBar.className = 'progress-bar bg-success';

                                if (statusData.error) {
                                    // Failed
                                    resultDiv.innerHTML = `<div class="alert alert-danger"><i class="bi bi-x-circle"></i> ${statusData.error}</div>`;
                                    submitBtn.disabled = false;
                                    submitBtn.innerHTML = '<i class="bi bi-plus-lg"></i> Create';
                                } else {
                                    // Success
                                    resultDiv.innerHTML = `<div class="alert alert-success"><i class="bi bi-check-circle"></i> Instance "${formData.name}" created successfully!</div>`;
                                    setTimeout(() => location.reload(), 2000);
                                }
                                resultDiv.style.display = 'block';
                            }
                        } else {
                            clearInterval(createPollingInterval);
                            throw new Error(statusData.message || 'Failed to get status');
                        }
                    } catch (error) {
                        clearInterval(createPollingInterval);
                        throw error;
                    }
                }, 1000); // Poll every second

            } catch (error) {
                clearInterval(createPollingInterval);
                progressBar.className = 'progress-bar bg-danger';
                progressBar.style.width = '100%';
                progressText.textContent = 'Failed';
                resultDiv.innerHTML = `<div class="alert alert-danger"><i class="bi bi-x-circle"></i> Error: ${error.message}</div>`;
                resultDiv.style.display = 'block';
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i class="bi bi-plus-lg"></i> Create';
            }
        });
    }
});

async function startInstance(name) {
    const resultDiv = document.getElementById('action-result');
    resultDiv.style.display = 'block';
    resultDiv.innerHTML = '<div class="alert alert-info"><i class="bi bi-hourglass-split"></i> Starting instance...</div>';

    try {
        const response = await fetch(`/instances/${name}/start`, { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            resultDiv.innerHTML = `<div class="alert alert-success"><i class="bi bi-check-circle"></i> ${data.message}</div>`;
            setTimeout(() => location.reload(), 1500);
        } else {
            resultDiv.innerHTML = `<div class="alert alert-danger"><i class="bi bi-x-circle"></i> ${data.message}</div>`;
        }
    } catch (error) {
        resultDiv.innerHTML = `<div class="alert alert-danger"><i class="bi bi-x-circle"></i> Error: ${error.message}</div>`;
    }
}

async function stopInstance(name) {
    const resultDiv = document.getElementById('action-result');
    resultDiv.style.display = 'block';
    resultDiv.innerHTML = '<div class="alert alert-info"><i class="bi bi-hourglass-split"></i> Stopping instance...</div>';

    try {
        const response = await fetch(`/instances/${name}/stop`, { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            resultDiv.innerHTML = `<div class="alert alert-success"><i class="bi bi-check-circle"></i> ${data.message}</div>`;
            setTimeout(() => location.reload(), 1500);
        } else {
            resultDiv.innerHTML = `<div class="alert alert-danger"><i class="bi bi-x-circle"></i> ${data.message}</div>`;
        }
    } catch (error) {
        resultDiv.innerHTML = `<div class="alert alert-danger"><i class="bi bi-x-circle"></i> Error: ${error.message}</div>`;
    }
}

// Delete instance functions
let instanceToDelete = null;
const deleteModal = new bootstrap.Modal(document.getElementById('deleteModal'));

function confirmDelete(name, status) {
    instanceToDelete = name;
    document.getElementById('deleteInstanceName').textContent = name;
    
    const deleteBtn = document.getElementById('deleteConfirmBtn');
    const stopWarning = document.getElementById('stopWarning');
    
    // Disable delete button if instance is running
    if (status === 'Running') {
        stopWarning.style.display = 'block';
        stopWarning.innerHTML = '<i class="bi bi-info-circle"></i> <strong>Note:</strong> Instance must be stopped before deletion.';
        deleteBtn.disabled = true;
        deleteBtn.title = 'Stop the instance first before deleting';
    } else {
        stopWarning.style.display = 'none';
        deleteBtn.disabled = false;
        deleteBtn.title = '';
    }
    
    deleteModal.show();
}

async function deleteInstance() {
    if (!instanceToDelete) return;

    const resultDiv = document.getElementById('action-result');

    deleteModal.hide();
    resultDiv.style.display = 'block';
    resultDiv.innerHTML = '<div class="alert alert-info"><i class="bi bi-hourglass-split"></i> Deleting instance...</div>';

    try {
        const response = await fetch(`/instances/${instanceToDelete}/delete`, {
            method: 'DELETE'
        });
        const data = await response.json();

        if (data.success) {
            resultDiv.innerHTML = `<div class="alert alert-success"><i class="bi bi-check-circle"></i> ${data.message}</div>`;
            setTimeout(() => location.reload(), 1500);
        } else {
            resultDiv.innerHTML = `<div class="alert alert-danger"><i class="bi bi-x-circle"></i> ${data.message}</div>`;
        }
    } catch (error) {
        resultDiv.innerHTML = `<div class="alert alert-danger"><i class="bi bi-x-circle"></i> Error: ${error.message}</div>`;
    }

    instanceToDelete = null;
}

// ============== Bulk Operations ==============

// Track selected instances
function toggleSelectAll() {
    const selectAllCheckbox = document.getElementById('select-all');
    const checkboxes = document.querySelectorAll('.instance-checkbox');
    
    checkboxes.forEach(cb => {
        cb.checked = selectAllCheckbox.checked;
    });
    
    updateSelectedCount();
}

function updateSelectedCount() {
    const checkboxes = document.querySelectorAll('.instance-checkbox:checked');
    const countElement = document.getElementById('selected-count');
    const selectAllCheckbox = document.getElementById('select-all');
    const allCheckboxes = document.querySelectorAll('.instance-checkbox');
    
    countElement.textContent = `${checkboxes.length} selected`;
    
    // Update "select all" checkbox state
    selectAllCheckbox.checked = checkboxes.length > 0 && checkboxes.length === allCheckboxes.length;
}

// Bulk Create Functions
let bulkOperationId = null;
let bulkPollingInterval = null;

async function checkBulkPreflight() {
    const namesText = document.getElementById('bulk_names').value.trim();
    if (!namesText) {
        document.getElementById('bulk-preflight-result').innerHTML = 
            '<div class="alert alert-warning"><i class="bi bi-exclamation-triangle"></i> Please enter instance names first</div>';
        document.getElementById('bulkCreateStartBtn').disabled = true;
        return;
    }
    
    const names = namesText.split(/[\n,]+/).map(n => n.trim()).filter(n => n);
    const cpu = parseInt(document.getElementById('bulk_cpu').value);
    const ram = parseInt(document.getElementById('bulk_ram').value);
    const disk = parseInt(document.getElementById('bulk_disk').value);
    
    const resultDiv = document.getElementById('bulk-preflight-result');
    resultDiv.innerHTML = '<div class="alert alert-info"><i class="bi bi-hourglass-split"></i> Checking prerequisites...</div>';
    
    try {
        const params = new URLSearchParams({
            names: names.join(','),
            cpu: cpu.toString(),
            ram: ram.toString(),
            disk: disk.toString()
        });
        
        const response = await fetch(`/instances/bulk/preflight?${params}`);
        const checks = await response.json();
        
        let html = '';
        
        if (checks.passed) {
            html = '<div class="alert alert-success"><i class="bi bi-check-circle"></i> All pre-flight checks passed!</div>';
            html += `<div class="alert alert-info mt-2 mb-0">
                <strong>Resources required:</strong><br>
                CPU: ${checks.resources_requested?.cpu || 0} vCPUs | 
                RAM: ${checks.resources_requested?.ram_gb || 0} GB | 
                Disk: ${checks.resources_requested?.disk_gb || 0} GB
            </div>`;
            document.getElementById('bulkCreateStartBtn').disabled = false;
        } else {
            html = '<div class="alert alert-danger"><i class="bi bi-x-circle"></i> Pre-flight checks failed:</div><ul class="mb-0">';
            checks.errors.forEach(err => {
                html += `<li>${err}</li>`;
            });
            checks.warnings.forEach(warn => {
                html += `<li class="text-warning">${warn}</li>`;
            });
            html += '</ul>';
            document.getElementById('bulkCreateStartBtn').disabled = true;
        }
        
        // Add system info
        const infoLines = [];
        if (checks.disk_free_gb !== undefined) {
            infoLines.push(`Disk: ${checks.disk_free_gb} GB free`);
        }
        if (checks.ram_available_gb !== undefined) {
            infoLines.push(`RAM: ${checks.ram_available_gb} GB available`);
        }
        if (checks.cpu_logical_cores !== undefined) {
            infoLines.push(`CPU: ${checks.cpu_logical_cores} cores`);
        }
        if (checks.existing_instances !== undefined) {
            infoLines.push(`Existing VMs: ${checks.existing_instances} (${checks.running_instances} running)`);
        }
        
        if (infoLines.length > 0) {
            html += `<div class="alert alert-info mt-2 mb-0"><i class="bi bi-pc-display"></i> <strong>System Status:</strong><br>${infoLines.join(' | ')}</div>`;
        }
        
        resultDiv.innerHTML = html;
    } catch (error) {
        resultDiv.innerHTML = `<div class="alert alert-danger"><i class="bi bi-x-circle"></i> Error: ${error.message}</div>`;
        document.getElementById('bulkCreateStartBtn').disabled = true;
    }
}

async function startBulkCreate() {
    const namesText = document.getElementById('bulk_names').value.trim();
    const names = namesText.split(/[\n,]+/).map(n => n.trim()).filter(n => n);
    
    if (names.length === 0) {
        alert('Please enter at least one instance name');
        return;
    }
    
    const formData = {
        names: names,
        cpu: parseInt(document.getElementById('bulk_cpu').value),
        ram: parseInt(document.getElementById('bulk_ram').value),
        disk: parseInt(document.getElementById('bulk_disk').value),
        type: document.getElementById('bulk_type').value
    };
    
    // Close the bulk create modal and show progress modal
    const bulkCreateModal = bootstrap.Modal.getInstance(document.getElementById('bulkCreateModal'));
    bulkCreateModal.hide();
    
    const progressModal = new bootstrap.Modal(document.getElementById('bulkProgressModal'));
    progressModal.show();
    
    document.getElementById('bulk-progress-bar').style.width = '0%';
    document.getElementById('bulk-progress-message').textContent = `Starting bulk creation of ${names.length} instances...`;
    document.getElementById('bulk-progress-details').textContent = '';
    
    try {
        const response = await fetch('/instances/bulk/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });
        
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.message);
        }
        
        bulkOperationId = data.operation_id;
        
        // Start polling for progress
        bulkPollingInterval = setInterval(pollBulkOperation, 2000);
        
    } catch (error) {
        clearInterval(bulkPollingInterval);
        document.getElementById('bulk-progress-message').textContent = 'Failed to start bulk creation';
        document.getElementById('bulk-progress-bar').className = 'progress-bar bg-danger';
        setTimeout(() => location.reload(), 3000);
    }
}

async function pollBulkOperation() {
    if (!bulkOperationId) return;

    try {
        const response = await fetch(`/instances/bulk/status/${bulkOperationId}`);
        const data = await response.json();

        if (data.success) {
            const op = data.operation;
            const progressBar = document.getElementById('bulk-progress-bar');
            const progressMessage = document.getElementById('bulk-progress-message');
            const progressDetails = document.getElementById('bulk-progress-details');

            progressBar.style.width = `${op.progress}%`;
            progressMessage.textContent = op.message;
            progressDetails.textContent = `Completed: ${op.completed}/${op.total} | Failed: ${op.failed}`;

            if (op.done) {
                clearInterval(bulkPollingInterval);

                if (op.error) {
                    progressBar.className = 'progress-bar bg-danger';
                    progressMessage.textContent = `Failed: ${op.error}`;
                } else if (op.failed > 0) {
                    progressBar.className = 'progress-bar bg-warning';
                    progressMessage.textContent = 'Completed with errors';
                } else {
                    progressBar.className = 'progress-bar bg-success';
                    // Dynamic success message based on operation type
                    const typeLabels = {
                        'bulk_create': 'Bulk creation',
                        'bulk_start': 'Bulk start',
                        'bulk_stop': 'Bulk stop',
                        'bulk_delete': 'Bulk deletion'
                    };
                    const label = typeLabels[op.type] || 'Bulk operation';
                    progressMessage.textContent = `${label} completed successfully!`;
                }

                // Close modal after delay and reload
                setTimeout(() => {
                    const progressModal = bootstrap.Modal.getInstance(document.getElementById('bulkProgressModal'));
                    progressModal.hide();
                    location.reload();
                }, 3000);
            }
        }
    } catch (error) {
        console.error('Error polling bulk operation:', error);
    }
}

// Bulk Stop/Delete Functions
async function bulkStartSelected() {
    const checkboxes = document.querySelectorAll('.instance-checkbox:checked');
    const names = Array.from(checkboxes).map(cb => cb.value);
    
    if (names.length === 0) {
        alert('Please select at least one instance');
        return;
    }
    
    if (!confirm(`Start ${names.length} selected instance(s)?`)) return;
    
    await executeBulkOperation('start', names);
}

async function bulkStopSelected() {
    const checkboxes = document.querySelectorAll('.instance-checkbox:checked');
    const names = Array.from(checkboxes).map(cb => cb.value);
    
    if (names.length === 0) {
        alert('Please select at least one instance');
        return;
    }
    
    if (!confirm(`Stop ${names.length} selected instance(s)?`)) return;
    
    await executeBulkOperation('stop', names);
}

async function bulkDeleteSelected() {
    const checkboxes = document.querySelectorAll('.instance-checkbox:checked');
    const names = Array.from(checkboxes).map(cb => cb.value);
    const statuses = Array.from(checkboxes).map(cb => cb.dataset.status);
    
    if (names.length === 0) {
        alert('Please select at least one instance');
        return;
    }
    
    // Check for running instances
    const runningNames = names.filter((_, i) => statuses[i] === 'Running');
    
    if (runningNames.length > 0) {
        const confirmMsg = `${runningNames.length} of the selected instance(s) are still running:\n${runningNames.join(', ')}\n\n` +
                          `They will be stopped before deletion.\n\n` +
                          `Do you want to proceed?`;
        if (!confirm(confirmMsg)) return;
    } else {
        if (!confirm(`Delete ${names.length} selected instance(s)? This cannot be undone!`)) return;
    }
    
    await executeBulkOperation('delete', names);
}

async function bulkStartAll() {
    if (!confirm('Start ALL stopped instances?')) return;
    
    await executeBulkOperation('start', [], true);
}

async function bulkStopAll() {
    if (!confirm('Stop ALL running instances?')) return;
    
    await executeBulkOperation('stop', [], true);
}

async function bulkDeleteAll() {
    if (!confirm('Delete ALL stopped instances? This cannot be undone!')) return;
    
    await executeBulkOperation('delete', [], true);
}

async function executeBulkOperation(action, names, all = false) {
    const progressModal = new bootstrap.Modal(document.getElementById('bulkProgressModal'));
    progressModal.show();
    
    document.getElementById('bulk-progress-bar').style.width = '0%';
    const actionText = action.charAt(0).toUpperCase() + action.slice(1);
    document.getElementById('bulk-progress-message').textContent = all ? 
        `${actionText}ing all instances...` :
        `${actionText}ing ${names.length} instances...`;
    document.getElementById('bulk-progress-details').textContent = '';
    
    try {
        const response = await fetch(`/instances/bulk/${action}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ names, all })
        });
        
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.message);
        }
        
        bulkOperationId = data.operation_id;
        bulkPollingInterval = setInterval(pollBulkOperation, 2000);
        
    } catch (error) {
        clearInterval(bulkPollingInterval);
        document.getElementById('bulk-progress-message').textContent = `Failed: ${error.message}`;
        document.getElementById('bulk-progress-bar').className = 'progress-bar bg-danger';
        setTimeout(() => {
            progressModal.hide();
            location.reload();
        }, 3000);
    }
}
