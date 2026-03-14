// Instance creation with progress tracking
let createPollingInterval = null;

document.addEventListener('DOMContentLoaded', function() {
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
