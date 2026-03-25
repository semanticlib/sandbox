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
async function loadImages(instanceType = 'virtual-machine') {
    const select = document.getElementById('image_select');
    const descField = document.getElementById('image_description');
    const fpField = document.getElementById('image_fingerprint');
    const aliasField = document.getElementById('image_alias');

    select.disabled = true;
    select.innerHTML = '<option>Loading...</option>';

    try {
        const response = await fetch(`/settings/vm/images?instance_type=${instanceType}`);
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

// Load available LXD container images
async function loadContainerImages() {
    const select = document.getElementById('container_image_select');
    const descField = document.getElementById('container_image_description');
    const fpField = document.getElementById('container_image_fingerprint');
    const aliasField = document.getElementById('container_image_alias');

    select.disabled = true;
    select.innerHTML = '<option>Loading...</option>';

    try {
        const response = await fetch('/settings/vm/images?instance_type=container');
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

// Load cloud-init template for containers
async function loadContainerCloudInitTemplate() {
    const cloudInitField = document.getElementById('container_cloud_init');
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

// Load connection templates
async function loadConnectionTemplates() {
    const sshConfigField = document.getElementById('ssh_config_template');

    try {
        const response = await fetch('/settings/connection-templates');
        const data = await response.json();

        if (data.success) {
            sshConfigField.value = data.ssh_config_template;
        }
    } catch (error) {
        console.error('Failed to load connection templates:', error);
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

// Handle container image selection
function onContainerImageSelect() {
    const select = document.getElementById('container_image_select');
    const descField = document.getElementById('container_image_description');
    const fpField = document.getElementById('container_image_fingerprint');
    const aliasField = document.getElementById('container_image_alias');

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
    const containerSuccess = document.getElementById('container-success')?.value || '';
    const containerError = document.getElementById('container-error')?.value || '';
    const templatesSuccess = document.getElementById('templates-success')?.value || '';
    const templatesError = document.getElementById('templates-error')?.value || '';

    if (templatesSuccess || templatesError) {
        const templatesTab = new bootstrap.Tab(document.getElementById('connection-templates-tab'));
        templatesTab.show();
        // Load templates when tab is shown
        loadConnectionTemplates();
    } else if (containerSuccess || containerError) {
        const containerTab = new bootstrap.Tab(document.getElementById('container-settings-tab'));
        containerTab.show();
        // Load container images when container tab is shown
        loadContainerImages();
    } else if (vmSuccess || vmError) {
        const vmTab = new bootstrap.Tab(document.getElementById('vm-settings-tab'));
        vmTab.show();
        // Load images when VM tab is shown
        loadImages();
    } else if (passwordSuccess || passwordError) {
        const passwordTab = new bootstrap.Tab(document.getElementById('password-tab'));
        passwordTab.show();
    }

    // Load connection templates when tab is clicked
    const connectionTemplatesTab = document.getElementById('connection-templates-tab');
    if (connectionTemplatesTab) {
        connectionTemplatesTab.addEventListener('shown.bs.tab', function() {
            loadConnectionTemplates();
        });
    }

    // Load VM images when VM tab is shown
    const vmSettingsTab = document.getElementById('vm-settings-tab');
    if (vmSettingsTab) {
        vmSettingsTab.addEventListener('shown.bs.tab', function() {
            loadImages();
        });
    }

    // Load container images when Container tab is shown
    const containerSettingsTab = document.getElementById('container-settings-tab');
    if (containerSettingsTab) {
        containerSettingsTab.addEventListener('shown.bs.tab', function() {
            loadContainerImages();
        });
    }
});


// ============================================================
// LXD Profile Management
// ============================================================

let _currentProfileName = null;
let _profilesLoaded = false;

async function loadProfilesTab() {
    _profilesLoaded = true;
    const loading = document.getElementById('profile-list-loading');
    const list    = document.getElementById('profile-list');

    loading.style.display = 'block';
    list.style.display    = 'none';
    list.innerHTML        = '';

    try {
        const res  = await fetch('/api/lxd/profiles');
        const data = await res.json();

        loading.style.display = 'none';

        if (!data.success) {
            list.style.display = 'block';
            list.innerHTML = `<li class="list-group-item text-danger"><i class="bi bi-x-circle"></i> ${data.message}</li>`;
            return;
        }

        if (!data.profiles.length) {
            list.style.display = 'block';
            list.innerHTML = '<li class="list-group-item text-muted">No profiles found</li>';
            return;
        }

        data.profiles.forEach(p => {
            const li = document.createElement('li');
            li.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center';
            li.dataset.name = p.name;
            li.style.cursor = 'pointer';

            const specs = [
                p.cpu    ? `${p.cpu}c`    : null,
                p.memory ? `${p.memory}G` : null,
                p.disk   ? `${p.disk}G`   : null,
            ].filter(Boolean).join(' / ');

            li.innerHTML = `
                <div>
                    <strong>${p.name}</strong>
                    ${p.description ? `<br><small class="text-muted">${p.description}</small>` : ''}
                </div>
                <span class="text-muted small">${specs}${p.has_cloud_init ? ' ☁' : ''}</span>`;
            li.addEventListener('click', () => selectProfile(p.name));
            list.appendChild(li);
        });

        list.style.display = 'block';
    } catch (err) {
        loading.style.display = 'none';
        list.style.display    = 'block';
        list.innerHTML = `<li class="list-group-item text-danger"><i class="bi bi-x-circle"></i> ${err.message}</li>`;
    }
}

async function selectProfile(name) {
    // Highlight in list
    document.querySelectorAll('#profile-list .list-group-item').forEach(li => {
        li.classList.toggle('active', li.dataset.name === name);
    });

    _currentProfileName = name;
    hideNewProfileForm();

    // Show edit card, hide placeholder
    document.getElementById('profile-placeholder').style.display  = 'none';
    document.getElementById('profile-edit-card').style.display    = 'block';
    document.getElementById('profile-edit-name').textContent      = name;
    document.getElementById('profile-alert').style.display        = 'none';

    // Disable delete button for 'default'
    document.getElementById('profile-delete-btn').disabled = (name === 'default');

    // Fetch full profile details (includes cloud-init text)
    try {
        const res  = await fetch(`/api/lxd/profiles/${encodeURIComponent(name)}`);
        const data = await res.json();
        if (!data.success) { showProfileAlert('danger', data.message); return; }
        const p = data.profile;
        document.getElementById('pe-description').value = p.description || '';
        document.getElementById('pe-cpu').value          = p.cpu    ?? '';
        document.getElementById('pe-memory').value       = p.memory ?? '';
        document.getElementById('pe-disk').value         = p.disk   ?? '';
        document.getElementById('pe-cloud-init').value   = p.cloud_init || '';
    } catch (err) {
        showProfileAlert('danger', `Failed to load profile: ${err.message}`);
    }
}

async function saveProfile() {
    if (!_currentProfileName) return;
    const payload = {
        description: document.getElementById('pe-description').value,
        cpu:         parseInt(document.getElementById('pe-cpu').value)    || null,
        memory:      parseInt(document.getElementById('pe-memory').value) || null,
        disk:        parseInt(document.getElementById('pe-disk').value)   || null,
        cloud_init:  document.getElementById('pe-cloud-init').value,
    };

    try {
        const res  = await fetch(`/api/lxd/profiles/${encodeURIComponent(_currentProfileName)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (data.success) {
            showProfileAlert('success', `Profile '${_currentProfileName}' saved.`);
            loadProfilesTab();          // refresh list badges
        } else {
            showProfileAlert('danger', data.message);
        }
    } catch (err) {
        showProfileAlert('danger', err.message);
    }
}

async function createProfile() {
    const name = document.getElementById('pn-name').value.trim();
    if (!name) { showProfileAlert('danger', 'Profile name is required.'); return; }

    const payload = {
        name,
        description: document.getElementById('pn-description').value,
        cpu:         parseInt(document.getElementById('pn-cpu').value)    || null,
        memory:      parseInt(document.getElementById('pn-memory').value) || null,
        disk:        parseInt(document.getElementById('pn-disk').value)   || null,
        cloud_init:  document.getElementById('pn-cloud-init').value,
    };

    try {
        const res  = await fetch('/api/lxd/profiles', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (data.success) {
            showProfileAlert('success', `Profile '${name}' created.`);
            hideNewProfileForm();
            _profilesLoaded = false;
            loadProfilesTab();
        } else {
            showProfileAlert('danger', data.message);
        }
    } catch (err) {
        showProfileAlert('danger', err.message);
    }
}

async function deleteProfile() {
    if (!_currentProfileName || _currentProfileName === 'default') return;
    if (!confirm(`Delete profile '${_currentProfileName}'? This cannot be undone.`)) return;

    try {
        const res  = await fetch(`/api/lxd/profiles/${encodeURIComponent(_currentProfileName)}`, {
            method: 'DELETE'
        });
        const data = await res.json();
        if (data.success) {
            _currentProfileName = null;
            document.getElementById('profile-edit-card').style.display = 'none';
            document.getElementById('profile-placeholder').style.display = 'block';
            showProfileAlert('success', data.message);
            _profilesLoaded = false;
            loadProfilesTab();
        } else {
            showProfileAlert('danger', data.message);
        }
    } catch (err) {
        showProfileAlert('danger', err.message);
    }
}

function showNewProfileForm() {
    document.getElementById('profile-new-card').style.display  = 'block';
    document.getElementById('profile-edit-card').style.display = 'none';
    document.getElementById('profile-placeholder').style.display = 'none';
    document.getElementById('profile-alert').style.display     = 'none';
    // Clear fields
    ['pn-name','pn-description','pn-cpu','pn-memory','pn-disk','pn-cloud-init']
        .forEach(id => { document.getElementById(id).value = ''; });
    // Deselect list item
    document.querySelectorAll('#profile-list .active').forEach(li => li.classList.remove('active'));
    _currentProfileName = null;
}

function hideNewProfileForm() {
    document.getElementById('profile-new-card').style.display = 'none';
    if (!_currentProfileName) {
        document.getElementById('profile-placeholder').style.display = 'block';
    }
}

async function loadDefaultCloudInit(targetId) {
    try {
        const res  = await fetch('/settings/vm/template');
        const data = await res.json();
        if (data.success) {
            document.getElementById(targetId).value = data.template;
        }
    } catch (err) {
        console.error('Failed to load default cloud-init:', err);
    }
}

function showProfileAlert(type, message) {
    const el = document.getElementById('profile-alert');
    el.style.display = 'block';
    el.innerHTML = `<div class="alert alert-${type} alert-dismissible mb-3">
        <i class="bi bi-${type === 'success' ? 'check-circle' : 'x-circle'}"></i> ${message}
        <button type="button" class="btn-close" onclick="this.parentElement.parentElement.style.display='none'"></button>
    </div>`;
}
