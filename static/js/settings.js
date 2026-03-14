function toggleConnectionFields() {
    const connectionType = document.getElementById('connection_type').value;
    const serverUrlGroup = document.getElementById('server-url-group');
    const socketPathGroup = document.getElementById('socket-path-group');
    const serverUrlInput = document.getElementById('server_url');
    const useSocketInput = document.getElementById('use_socket');
    const verifySslGroup = document.getElementById('verify-ssl-group');
    const clientCertGroup = document.getElementById('client-cert-group');
    const clientKeyGroup = document.getElementById('client-key-group');

    if (connectionType === 'socket') {
        serverUrlGroup.style.display = 'none';
        socketPathGroup.style.display = 'block';
        serverUrlInput.required = false;
        useSocketInput.value = 'on';
        verifySslGroup.style.display = 'none';
        clientCertGroup.style.display = 'none';
        clientKeyGroup.style.display = 'none';
    } else {
        serverUrlGroup.style.display = 'block';
        socketPathGroup.style.display = 'none';
        serverUrlInput.required = true;
        useSocketInput.value = 'off';
        verifySslGroup.style.display = 'block';
        clientCertGroup.style.display = 'block';
        clientKeyGroup.style.display = 'block';
    }
}

async function testConnection() {
    const resultDiv = document.getElementById('test-result');
    resultDiv.style.display = 'block';
    resultDiv.innerHTML = '<div class="alert alert-info"><i class="bi bi-hourglass-split"></i> Testing connection...</div>';

    try {
        const response = await fetch('/settings/lxd/test', { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            resultDiv.innerHTML = `
                <div class="alert alert-success">
                    <i class="bi bi-check-circle"></i> ${data.message}
                </div>`;
        } else {
            resultDiv.innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-x-circle"></i> ${data.message}
                </div>`;
        }
    } catch (error) {
        resultDiv.innerHTML = `
            <div class="alert alert-danger">
                <i class="bi bi-x-circle"></i> Connection failed: ${error.message}
            </div>`;
    }
}

async function generateCertificate() {
    const certField = document.getElementById('client_cert');
    const keyField = document.getElementById('client_key');
    const alertDiv = document.getElementById('cert-alert');

    certField.disabled = true;
    keyField.disabled = true;
    alertDiv.style.display = 'block';
    alertDiv.innerHTML = '<div class="alert alert-info"><i class="bi bi-hourglass-split"></i> Generating certificate...</div>';

    try {
        const response = await fetch('/settings/lxd/generate-cert', { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            certField.value = data.certificate;
            keyField.value = data.key;
            certField.disabled = false;
            keyField.disabled = false;
            alertDiv.innerHTML = `
                <div class="alert alert-success">
                    <i class="bi bi-check-circle"></i> Certificate generated!
                    <strong>Copy the certificate above</strong> and add it to LXD using:
                    <code class="d-block mt-2 bg-light p-2 rounded">lxc config trust add</code>
                </div>`;
        } else {
            alertDiv.innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-x-circle"></i> Failed: ${data.message}
                </div>`;
            certField.disabled = false;
            keyField.disabled = false;
        }
    } catch (error) {
        alertDiv.innerHTML = `
            <div class="alert alert-danger">
                <i class="bi bi-x-circle"></i> Error: ${error.message}
            </div>`;
        certField.disabled = false;
        keyField.disabled = false;
    }
}

async function loadCloudInitTemplate() {
    const cloudInitField = document.getElementById('cloud_init');
    cloudInitField.disabled = true;
    cloudInitField.placeholder = 'Loading template...';
    
    try {
        const response = await fetch('/settings/vm/template');
        const data = await response.json();
        
        if (data.success) {
            cloudInitField.value = data.template;
        } else {
            cloudInitField.value = '# Failed to load template';
        }
    } catch (error) {
        cloudInitField.value = `# Error loading template: ${error.message}`;
    } finally {
        cloudInitField.disabled = false;
    }
}

// Load available LXD images
async function loadImages() {
    const select = document.getElementById('image_select');
    const descField = document.getElementById('image_description');
    const fpField = document.getElementById('image_fingerprint');
    const aliasField = document.getElementById('image_alias');
    
    select.disabled = true;
    select.innerHTML = '<option>Loading...</option>';
    
    try {
        const response = await fetch('/settings/vm/images');
        const data = await response.json();
        
        if (data.success && data.images.length > 0) {
            select.innerHTML = '<option value="">-- Select an image --</option>';
            
            data.images.forEach(img => {
                const aliasText = img.aliases.length > 0 ? ` (${img.aliases.join(', ')})` : '';
                const option = document.createElement('option');
                option.value = img.fingerprint;
                option.textContent = `${img.description}${aliasText}`;
                option.dataset.fullFingerprint = img.full_fingerprint;
                option.dataset.alias = img.aliases.length > 0 ? img.aliases[0] : '';
                option.dataset.description = img.description;
                select.appendChild(option);
            });
            
            // Restore previously selected image
            if (fpField.value) {
                for (let opt of select.options) {
                    if (opt.dataset.fullFingerprint === fpField.value || opt.value === fpField.value) {
                        opt.selected = true;
                        descField.value = opt.dataset.description;
                        aliasField.value = opt.dataset.alias;
                        break;
                    }
                }
            }
        } else {
            select.innerHTML = '<option value="">No images found</option>';
        }
    } catch (error) {
        select.innerHTML = `<option value="">Error loading images</option>`;
        console.error('Failed to load images:', error);
    } finally {
        select.disabled = false;
    }
}

// Handle image selection
function onImageSelect() {
    const select = document.getElementById('image_select');
    const descField = document.getElementById('image_description');
    const fpField = document.getElementById('image_fingerprint');
    const aliasField = document.getElementById('image_alias');
    
    const selectedOption = select.options[select.selectedIndex];
    
    if (selectedOption.value) {
        descField.value = selectedOption.dataset.description || selectedOption.textContent;
        fpField.value = selectedOption.dataset.fullFingerprint || selectedOption.value;
        aliasField.value = selectedOption.dataset.alias || '';
    } else {
        descField.value = '';
        fpField.value = '';
        aliasField.value = '';
    }
}

// Initialize connection fields on page load
document.addEventListener('DOMContentLoaded', function() {
    // Unix Socket is the default selection in the dropdown
    toggleConnectionFields();

    // Always show LXD Connection tab by default on fresh page load
    const lxdTab = new bootstrap.Tab(document.getElementById('lxd-tab'));
    lxdTab.show();

    // Auto-switch to specific tab if there are related messages
    const passwordSuccess = document.getElementById('password-success')?.value || '';
    const passwordError = document.getElementById('password-error')?.value || '';
    const vmSuccess = document.getElementById('vm-success')?.value || '';
    const vmError = document.getElementById('vm-error')?.value || '';
    const templatesSuccess = document.getElementById('templates-success')?.value || '';
    const templatesError = document.getElementById('templates-error')?.value || '';

    if (templatesSuccess || templatesError) {
        const templatesTab = new bootstrap.Tab(document.getElementById('connection-templates-tab'));
        templatesTab.show();
    } else if (vmSuccess || vmError) {
        const vmTab = new bootstrap.Tab(document.getElementById('vm-settings-tab'));
        vmTab.show();
        // Load images when VM tab is shown
        loadImages();
    } else if (passwordSuccess || passwordError) {
        const passwordTab = new bootstrap.Tab(document.getElementById('password-tab'));
        passwordTab.show();
    }
});
