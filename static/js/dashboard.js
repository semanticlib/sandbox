// Instance creation with progress tracking
let createPollingInterval = null;

// ============== Classroom Picker ==============

let _classroomCache = null;  // { id -> { name, image_type, lxd_profile, ... } }

async function loadClassrooms() {
    try {
        const res = await fetch('/api/classrooms');
        const data = await res.json();
        if (!data.success || !data.classrooms.length) return;

        _classroomCache = {};
        data.classrooms.forEach(c => { _classroomCache[c.id] = c; });

        const selectors = [
            document.getElementById('instance_classroom'),
            document.getElementById('bulk_classroom'),
        ];

        selectors.forEach(sel => {
            if (!sel) return;
            // Keep the placeholder option, clear the rest
            while (sel.options.length > 1) sel.remove(1);
            data.classrooms.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c.id;
                const typeIcon = c.image_type === 'virtual-machine' ? '🖥️' : '📦';
                const profileInfo = c.lxd_profile ? ` • ${c.lxd_profile}` : '';
                opt.textContent = `${typeIcon} ${c.name}${profileInfo}`;
                sel.appendChild(opt);
            });
        });
    } catch(e) {
        console.warn('Could not load classrooms:', e.message);
    }
}

/**
 * Apply selected classroom settings to form fields.
 * @param {'instance'|'bulk'} context
 */
function applyClassroom(context) {
    if (!_classroomCache) return;

    const prefix = context === 'bulk' ? 'bulk' : 'instance';
    const selEl = document.getElementById(
        context === 'bulk' ? 'bulk_classroom' : 'instance_classroom'
    );
    if (!selEl) return;

    const classroomId = selEl.value;
    if (!classroomId) return;  // No classroom selected, leave fields as-is

    const c = _classroomCache[classroomId];
    if (!c) return;

    // If classroom has an LXD profile, fetch its details and populate CPU/RAM/Disk
    if (c.lxd_profile) {
        fetch(`/api/lxd/profiles/${encodeURIComponent(c.lxd_profile)}`)
            .then(res => res.json())
            .then(data => {
                if (data.success && data.profile) {
                    const p = data.profile;
                    const cpuEl = document.getElementById(prefix === 'bulk' ? 'bulk_cpu' : 'instance_cpu');
                    const ramEl = document.getElementById(prefix === 'bulk' ? 'bulk_ram' : 'instance_ram');
                    const diskEl = document.getElementById(prefix === 'bulk' ? 'bulk_disk' : 'instance_disk');

                    if (p.cpu != null && cpuEl) cpuEl.value = p.cpu;
                    if (p.memory != null && ramEl) ramEl.value = p.memory;
                    if (p.disk != null && diskEl) diskEl.value = p.disk;
                }
            })
            .catch(err => console.warn('Failed to fetch profile details:', err));
    }
}

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
    loadClassrooms();
    const form = document.getElementById('create-instance-form');
    if (form) {
        form.addEventListener('submit', async function(e) {
            e.preventDefault();

            const submitBtn = form.querySelector('button[type="submit"]');
            const progressContainer = document.getElementById('create-progress-container');
            const progressBar = document.getElementById('create-progress-bar');
            const progressText = document.getElementById('create-progress-text');
            const resultDiv = document.getElementById('create-result');

            // Get classroom and derive type from it
            const classroomEl = form.instance_classroom;
            const classroomId = classroomEl.value;
            let instanceType = 'virtual-machine';  // default
            let lxdProfile = null;
            
            if (classroomId && _classroomCache && _classroomCache[classroomId]) {
                const classroom = _classroomCache[classroomId];
                instanceType = classroom.image_type || 'virtual-machine';
                lxdProfile = classroom.lxd_profile;
            }

            // Get form values
            const formData = {
                name: form.instance_name.value.trim(),
                cpu: parseInt(form.instance_cpu.value),
                ram: parseInt(form.instance_ram.value),
                disk: parseInt(form.instance_disk.value),
                type: instanceType,
                classroom_id: classroomId || null,
                lxd_profile: lxdProfile
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

// Single instance action modals
let instanceStartModal = null;
let instanceStopModal = null;
let pendingInstanceAction = null;

async function startInstance(name) {
    // Show modal confirmation
    document.getElementById('bulkStartMessage').textContent = 
        `Start instance "${name}"?`;
    
    // Remove old event listeners and add new one
    const confirmBtn = document.getElementById('bulkStartConfirmBtn');
    confirmBtn.replaceWith(confirmBtn.cloneNode(true));
    document.getElementById('bulkStartConfirmBtn').addEventListener('click', async function() {
        instanceStartModal.hide();
        await executeInstanceAction('start', name);
    });

    instanceStartModal = new bootstrap.Modal(document.getElementById('bulkStartModal'));
    instanceStartModal.show();
}

async function stopInstance(name) {
    // Show modal confirmation
    document.getElementById('bulkStopMessage').textContent = 
        `Stop instance "${name}"?`;
    
    // Remove old event listeners and add new one
    const confirmBtn = document.getElementById('bulkStopConfirmBtn');
    confirmBtn.replaceWith(confirmBtn.cloneNode(true));
    document.getElementById('bulkStopConfirmBtn').addEventListener('click', async function() {
        instanceStopModal.hide();
        await executeInstanceAction('stop', name);
    });

    instanceStopModal = new bootstrap.Modal(document.getElementById('bulkStopModal'));
    instanceStopModal.show();
}

async function executeInstanceAction(action, name) {
    const resultDiv = document.getElementById('action-result');
    const actionText = action.charAt(0).toUpperCase() + action.slice(1);
    resultDiv.style.display = 'block';
    resultDiv.innerHTML = `<div class="alert alert-info"><i class="bi bi-hourglass-split"></i> ${actionText}ing instance...</div>`;

    try {
        const response = await fetch(`/instances/${name}/${action}`, { method: 'POST' });
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

    if (checkboxes.length > 0) {
        countElement.classList.remove('d-none');
        document.getElementById('bulk-actions').classList.remove('d-none');
    } else {
        countElement.classList.add('d-none');
        document.getElementById('bulk-actions').classList.add('d-none');
    }
    
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
    
    // Expand patterns client-side for preview
    let instanceNames;
    try {
        const response = await fetch('/instances/api/expand-pattern', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pattern: namesText })
        });
        const data = await response.json();
        if (data.success) {
            instanceNames = data.names;
        } else {
            document.getElementById('bulk-preflight-result').innerHTML =
                `<div class="alert alert-danger"><i class="bi bi-x-circle"></i> ${data.message}</div>`;
            document.getElementById('bulkCreateStartBtn').disabled = true;
            return;
        }
    } catch (error) {
        // Fallback: simple split if API fails
        instanceNames = namesText.split(/[\n,]+/).map(n => n.trim()).filter(n => n);
    }
    
    const cpu = parseInt(document.getElementById('bulk_cpu').value);
    const ram = parseInt(document.getElementById('bulk_ram').value);
    const disk = parseInt(document.getElementById('bulk_disk').value);
    
    const resultDiv = document.getElementById('bulk-preflight-result');
    resultDiv.innerHTML = '<div class="alert alert-info"><i class="bi bi-hourglass-split"></i> Checking prerequisites...</div>';
    
    try {
        const params = new URLSearchParams({
            names: instanceNames.join(','),
            cpu: cpu.toString(),
            ram: ram.toString(),
            disk: disk.toString()
        });
        
        const response = await fetch(`/instances/bulk/preflight?${params}`);
        const checks = await response.json();
        
        let html = '';
        
        // Show preview of names to be created
        html += `<div class="alert alert-info">
            <strong>Will create ${instanceNames.length} instance(s):</strong><br>
            <small>${instanceNames.slice(0, 10).join(', ')}${instanceNames.length > 10 ? '...' : ''}</small>
        </div>`;
        
        if (checks.passed) {
            html += '<div class="alert alert-success"><i class="bi bi-check-circle"></i> All pre-flight checks passed!</div>';
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

    if (!namesText) {
        alert('Please enter at least one instance name');
        return;
    }

    // Get classroom and derive type from it
    const classroomEl = document.getElementById('bulk_classroom');
    const classroomId = classroomEl.value;
    let instanceType = 'virtual-machine';  // default
    let lxdProfile = null;
    
    if (classroomId && _classroomCache && _classroomCache[classroomId]) {
        const classroom = _classroomCache[classroomId];
        instanceType = classroom.image_type || 'virtual-machine';
        lxdProfile = classroom.lxd_profile;
    }

    // Expand patterns server-side by sending the raw pattern text
    const formData = {
        names: namesText,  // Send raw pattern (e.g., "vm-{01-03}")
        cpu: parseInt(document.getElementById('bulk_cpu').value),
        ram: parseInt(document.getElementById('bulk_ram').value),
        disk: parseInt(document.getElementById('bulk_disk').value),
        type: instanceType,
        classroom_id: classroomId || null,
        lxd_profile: lxdProfile
    };

    // Close the bulk create modal and show progress modal
    const bulkCreateModal = bootstrap.Modal.getInstance(document.getElementById('bulkCreateModal'));
    bulkCreateModal.hide();

    const progressModal = new bootstrap.Modal(document.getElementById('bulkProgressModal'));
    progressModal.show();

    // Get expanded count from preflight check for display
    const expandedCount = formData.names.split(/[\n,]+/).filter(n => n.trim()).length;
    document.getElementById('bulk-progress-bar').style.width = '0%';
    document.getElementById('bulk-progress-message').textContent = `Starting bulk creation...`;
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
        console.error('Bulk create error:', error);
        clearInterval(bulkPollingInterval);
        document.getElementById('bulk-progress-message').textContent = `Failed to start bulk creation: ${error.message}`;
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

// Bulk operation modal instances
let bulkStartModal = null;
let bulkStopModal = null;
let bulkDeleteModal = null;
let pendingBulkAction = null;

// Bulk Stop/Delete Functions
async function bulkStartSelected() {
    const checkboxes = document.querySelectorAll('.instance-checkbox:checked');
    const names = Array.from(checkboxes).map(cb => cb.value);

    if (names.length === 0) {
        alert('Please select at least one instance');
        return;
    }

    // Show modal confirmation
    document.getElementById('bulkStartMessage').textContent = 
        `Start ${names.length} selected instance(s)?`;
    
    // Remove old event listeners and add new one
    const confirmBtn = document.getElementById('bulkStartConfirmBtn');
    confirmBtn.replaceWith(confirmBtn.cloneNode(true));
    document.getElementById('bulkStartConfirmBtn').addEventListener('click', async function() {
        bulkStartModal.hide();
        await executeBulkOperation('start', names);
    });

    bulkStartModal = new bootstrap.Modal(document.getElementById('bulkStartModal'));
    bulkStartModal.show();
}

async function bulkStopSelected() {
    const checkboxes = document.querySelectorAll('.instance-checkbox:checked');
    const names = Array.from(checkboxes).map(cb => cb.value);

    if (names.length === 0) {
        alert('Please select at least one instance');
        return;
    }

    // Show modal confirmation
    document.getElementById('bulkStopMessage').textContent = 
        `Stop ${names.length} selected instance(s)?`;
    
    // Remove old event listeners and add new one
    const confirmBtn = document.getElementById('bulkStopConfirmBtn');
    confirmBtn.replaceWith(confirmBtn.cloneNode(true));
    document.getElementById('bulkStopConfirmBtn').addEventListener('click', async function() {
        bulkStopModal.hide();
        await executeBulkOperation('stop', names);
    });

    bulkStopModal = new bootstrap.Modal(document.getElementById('bulkStopModal'));
    bulkStopModal.show();
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

    // Update modal content
    document.getElementById('bulkDeleteMessage').textContent = 
        `Delete ${names.length} selected instance(s)? This cannot be undone!`;
    
    const runningWarning = document.getElementById('bulkDeleteRunningWarning');
    const instanceList = document.getElementById('bulkDeleteInstanceList');
    
    if (runningNames.length > 0) {
        runningWarning.style.display = 'block';
        runningWarning.innerHTML = `
            <i class="bi bi-info-circle"></i>
            <strong>Note:</strong> ${runningNames.length} running instance(s) will be stopped before deletion:
            <ul class="mb-0 mt-2">${runningNames.map(n => `<li>${n}</li>`).join('')}</ul>
        `;
    } else {
        runningWarning.style.display = 'none';
    }

    // Show instance list
    instanceList.innerHTML = `
        <strong>Instances to delete:</strong>
        <ul class="mb-0 mt-2">${names.map(n => `<li>${n}</li>`).join('')}</ul>
    `;
    
    // Remove old event listeners and add new one
    const confirmBtn = document.getElementById('bulkDeleteConfirmBtn');
    confirmBtn.replaceWith(confirmBtn.cloneNode(true));
    document.getElementById('bulkDeleteConfirmBtn').addEventListener('click', async function() {
        bulkDeleteModal.hide();
        await executeBulkOperation('delete', names);
    });

    bulkDeleteModal = new bootstrap.Modal(document.getElementById('bulkDeleteModal'));
    bulkDeleteModal.show();
}

async function bulkStartAll() {
    // Show modal confirmation
    document.getElementById('bulkStartMessage').textContent = 
        'Start ALL stopped instances?';
    
    // Remove old event listeners and add new one
    const confirmBtn = document.getElementById('bulkStartConfirmBtn');
    confirmBtn.replaceWith(confirmBtn.cloneNode(true));
    document.getElementById('bulkStartConfirmBtn').addEventListener('click', async function() {
        bulkStartModal.hide();
        await executeBulkOperation('start', [], true);
    });

    bulkStartModal = new bootstrap.Modal(document.getElementById('bulkStartModal'));
    bulkStartModal.show();
}

async function bulkStopAll() {
    // Show modal confirmation
    document.getElementById('bulkStopMessage').textContent = 
        'Stop ALL running instances?';
    
    // Remove old event listeners and add new one
    const confirmBtn = document.getElementById('bulkStopConfirmBtn');
    confirmBtn.replaceWith(confirmBtn.cloneNode(true));
    document.getElementById('bulkStopConfirmBtn').addEventListener('click', async function() {
        bulkStopModal.hide();
        await executeBulkOperation('stop', [], true);
    });

    bulkStopModal = new bootstrap.Modal(document.getElementById('bulkStopModal'));
    bulkStopModal.show();
}

async function bulkDeleteAll() {
    // Show modal confirmation
    document.getElementById('bulkDeleteMessage').textContent = 
        'Delete ALL stopped instances? This cannot be undone!';
    
    const runningWarning = document.getElementById('bulkDeleteRunningWarning');
    const instanceList = document.getElementById('bulkDeleteInstanceList');
    
    runningWarning.style.display = 'none';
    instanceList.innerHTML = '';
    
    // Remove old event listeners and add new one
    const confirmBtn = document.getElementById('bulkDeleteConfirmBtn');
    confirmBtn.replaceWith(confirmBtn.cloneNode(true));
    document.getElementById('bulkDeleteConfirmBtn').addEventListener('click', async function() {
        bulkDeleteModal.hide();
        await executeBulkOperation('delete', [], true);
    });

    bulkDeleteModal = new bootstrap.Modal(document.getElementById('bulkDeleteModal'));
    bulkDeleteModal.show();
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
