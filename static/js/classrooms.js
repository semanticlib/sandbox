// ============================================================
// Classroom Management
// ============================================================

let _currentClassroomId = null;
let _classroomsLoaded = false;
let _lxdProfilesCache = null;

async function loadClassroomsTab() {
    _classroomsLoaded = true;
    const loading = document.getElementById('classroom-list-loading');
    const list = document.getElementById('classroom-list');

    loading.style.display = 'block';
    list.style.display = 'none';
    list.innerHTML = '';

    // Load LXD profiles first
    await loadLXDProfilesForClassroom();

    try {
        const res = await fetch('/api/classrooms');
        const data = await res.json();

        loading.style.display = 'none';

        if (!data.success) {
            list.style.display = 'block';
            list.innerHTML = `<li class="list-group-item text-danger"><i class="bi bi-x-circle"></i> ${data.message}</li>`;
            return;
        }

        if (!data.classrooms.length) {
            list.style.display = 'block';
            list.innerHTML = '<li class="list-group-item text-muted">No classrooms found</li>';
            return;
        }

        data.classrooms.forEach(c => {
            const li = document.createElement('li');
            li.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center';
            li.dataset.id = c.id;
            li.style.cursor = 'pointer';

            const typeIcon = c.image_type === 'virtual-machine' ? '🖥️' : '📦';
            const profileInfo = c.lxd_profile ? ` • Profile: ${c.lxd_profile}` : '';

            li.innerHTML = `
                <div>
                    <strong>${c.name}</strong>
                    <br><small class="text-muted">${typeIcon} ${c.image_type === 'virtual-machine' ? 'VM' : 'Container'}${profileInfo}</small>
                </div>
                <i class="bi bi-chevron-right text-muted"></i>`;
            li.addEventListener('click', () => selectClassroom(c.id));
            list.appendChild(li);
        });

        list.style.display = 'block';
    } catch (err) {
        loading.style.display = 'none';
        list.style.display = 'block';
        list.innerHTML = `<li class="list-group-item text-danger"><i class="bi bi-x-circle"></i> ${err.message}</li>`;
    }
}

async function loadLXDProfilesForClassroom() {
    // If already loaded, skip
    if (_lxdProfilesCache) return;
    
    try {
        const res = await fetch('/api/lxd/profiles');
        const data = await res.json();
        if (data.success) {
            _lxdProfilesCache = data.profiles;
        }
    } catch (err) {
        console.warn('Could not load LXD profiles:', err.message);
    }
}

function populateProfileDropdowns(prefix) {
    const select = document.getElementById(`${prefix}-lxd-profile`);
    if (!select) {
        console.warn(`Dropdown ${prefix}-lxd-profile not found in DOM`);
        return;
    }
    if (!_lxdProfilesCache) {
        console.warn('LXD profiles cache is empty');
        return;
    }

    // Keep the first option, remove the rest
    while (select.options.length > 1) {
        select.remove(1);
    }

    _lxdProfilesCache.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.name;
        opt.textContent = p.name + (p.description ? ` - ${p.description}` : '');
        select.appendChild(opt);
    });
}

async function loadClassroomImages(context = 'edit') {
    const prefix = context === 'new' ? 'cn' : 'cc';
    const imageType = document.getElementById(`${prefix}-image-type`).value;
    const select = document.getElementById(`${prefix}-image-select`);

    select.innerHTML = '<option value="">— Select an image —</option>';
    select.disabled = true;

    try {
        const res = await fetch(`/settings/vm/images?instance_type=${imageType}`);
        const data = await res.json();

        if (data.success && data.images) {
            data.images.forEach(img => {
                const opt = document.createElement('option');
                opt.value = img.fingerprint;
                opt.textContent = img.description;
                opt.dataset.fullFingerprint = img.full_fingerprint;
                opt.dataset.alias = img.aliases.join(', ');
                select.appendChild(opt);
            });
            select.disabled = false;
        }
    } catch (err) {
        console.error('Failed to load images:', err);
    }
}

function onClassroomImageSelect(context = 'edit') {
    const prefix = context === 'new' ? 'cn' : 'cc';
    const select = document.getElementById(`${prefix}-image-select`);
    const descInput = document.getElementById(`${prefix}-image-description`);
    const fingerprintInput = document.getElementById(`${prefix}-image-fingerprint`);
    const aliasInput = document.getElementById(`${prefix}-image-alias`);

    const selected = select.options[select.selectedIndex];
    if (selected.value) {
        descInput.value = selected.textContent;
        fingerprintInput.value = selected.dataset.fullFingerprint;
        aliasInput.value = selected.dataset.alias;
    } else {
        descInput.value = '';
        fingerprintInput.value = '';
        aliasInput.value = '';
    }
}

async function selectClassroom(id) {
    // Highlight in list
    document.querySelectorAll('#classroom-list .list-group-item').forEach(li => {
        li.classList.toggle('active', li.dataset.id == id);
    });

    _currentClassroomId = id;
    hideNewClassroomForm();

    // Show edit card, hide placeholder
    document.getElementById('classroom-placeholder').style.display = 'none';
    document.getElementById('classroom-edit-card').style.display = 'block';
    document.getElementById('classroom-alert').style.display = 'none';

    // Ensure profiles are loaded, then populate dropdown
    await loadLXDProfilesForClassroom();
    populateProfileDropdowns('cc');

    // Fetch classroom details
    try {
        const res = await fetch(`/api/classrooms/${id}`);
        const data = await res.json();
        if (!data.success) { showClassroomAlert('danger', data.message); return; }
        const c = data.classroom;

        document.getElementById('classroom-edit-name').textContent = c.name;
        document.getElementById('cc-name').value = c.name;
        document.getElementById('cc-username').value = c.username;
        document.getElementById('cc-image-type').value = c.image_type;
        document.getElementById('cc-lxd-profile').value = c.lxd_profile || '';
        document.getElementById('cc-image-fingerprint').value = c.image_fingerprint || '';
        document.getElementById('cc-image-alias').value = c.image_alias || '';
        document.getElementById('cc-image-description').value = c.image_description || '';
        document.getElementById('cc-ssh-config').value = c.ssh_config_template || '';

        // Load images for the selected type
        await loadClassroomImages('edit');
    } catch (err) {
        showClassroomAlert('danger', `Failed to load classroom: ${err.message}`);
    }
}

async function saveClassroom() {
    if (!_currentClassroomId) return;

    const payload = {
        name: document.getElementById('cc-name').value.trim(),
        username: document.getElementById('cc-username').value.trim(),
        image_type: document.getElementById('cc-image-type').value,
        lxd_profile: document.getElementById('cc-lxd-profile').value || null,
        image_fingerprint: document.getElementById('cc-image-fingerprint').value || null,
        image_alias: document.getElementById('cc-image-alias').value || null,
        image_description: document.getElementById('cc-image-description').value || null,
        ssh_config_template: document.getElementById('cc-ssh-config').value,
    };

    if (!payload.name) {
        showClassroomAlert('danger', 'Classroom name is required.');
        return;
    }

    if (!payload.username) {
        showClassroomAlert('danger', 'Default username is required.');
        return;
    }

    try {
        const res = await fetch(`/api/classrooms/${_currentClassroomId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (data.success) {
            showClassroomAlert('success', `Classroom '${payload.name}' saved.`);
            document.getElementById('classroom-edit-name').textContent = payload.name;
            loadClassroomsTab();
        } else {
            showClassroomAlert('danger', data.message);
        }
    } catch (err) {
        showClassroomAlert('danger', err.message);
    }
}

async function createClassroom() {
    const name = document.getElementById('cn-name').value.trim();
    const username = document.getElementById('cn-username').value.trim();
    
    if (!name) { showClassroomAlert('danger', 'Classroom name is required.'); return; }
    if (!username) { showClassroomAlert('danger', 'Default username is required.'); return; }

    const payload = {
        name,
        username,
        image_type: document.getElementById('cn-image-type').value,
        lxd_profile: document.getElementById('cn-lxd-profile').value || null,
        image_fingerprint: document.getElementById('cn-image-fingerprint').value || null,
        image_alias: document.getElementById('cn-image-alias').value || null,
        image_description: document.getElementById('cn-image-description').value || null,
        ssh_config_template: document.getElementById('cn-ssh-config').value,
    };

    try {
        const res = await fetch('/api/classrooms', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (data.success) {
            showClassroomAlert('success', `Classroom '${name}' created.`);
            hideNewClassroomForm();
            _classroomsLoaded = false;
            loadClassroomsTab();
        } else {
            showClassroomAlert('danger', data.message);
        }
    } catch (err) {
        showClassroomAlert('danger', err.message);
    }
}

async function deleteClassroom() {
    if (!_currentClassroomId) return;
    if (!confirm(`Delete this classroom? This cannot be undone.`)) return;

    try {
        const res = await fetch(`/api/classrooms/${_currentClassroomId}`, {
            method: 'DELETE'
        });
        const data = await res.json();
        if (data.success) {
            _currentClassroomId = null;
            document.getElementById('classroom-edit-card').style.display = 'none';
            document.getElementById('classroom-placeholder').style.display = 'block';
            showClassroomAlert('success', data.message);
            _classroomsLoaded = false;
            loadClassroomsTab();
        } else {
            showClassroomAlert('danger', data.message);
        }
    } catch (err) {
        showClassroomAlert('danger', err.message);
    }
}

async function showNewClassroomForm() {
    document.getElementById('classroom-new-card').style.display = 'block';
    document.getElementById('classroom-edit-card').style.display = 'none';
    document.getElementById('classroom-placeholder').style.display = 'none';
    document.getElementById('classroom-alert').style.display = 'none';

    // Clear fields
    ['cn-name', 'cn-username', 'cn-image-description', 'cn-image-fingerprint', 'cn-image-alias', 'cn-ssh-config']
        .forEach(id => { document.getElementById(id).value = ''; });
    document.getElementById('cn-lxd-profile').value = '';

    // Ensure profiles are loaded, then populate dropdown
    await loadLXDProfilesForClassroom();
    populateProfileDropdowns('cn');

    // Deselect list item
    document.querySelectorAll('#classroom-list .active').forEach(li => li.classList.remove('active'));
    _currentClassroomId = null;

    // Load images
    loadClassroomImages('new');
}

function hideNewClassroomForm() {
    document.getElementById('classroom-new-card').style.display = 'none';
    if (!_currentClassroomId) {
        document.getElementById('classroom-placeholder').style.display = 'block';
    }
}

function showClassroomAlert(type, message) {
    const el = document.getElementById('classroom-alert');
    el.style.display = 'block';
    el.innerHTML = `<div class="alert alert-${type} alert-dismissible mb-3">
        <i class="bi bi-${type === 'success' ? 'check-circle' : 'x-circle'}"></i> ${message}
        <button type="button" class="btn-close" onclick="this.parentElement.parentElement.style.display='none'"></button>
    </div>`;
}

async function loadDefaultSSHConfig(targetId) {
    try {
        const res = await fetch('/classrooms/connection-templates');
        const data = await res.json();
        if (data.success) {
            document.getElementById(targetId).value = data.ssh_config_template;
        }
    } catch (err) {
        console.error('Failed to load default SSH config:', err);
    }
}


// ============================================================
// LXD Profile Management
// ============================================================

let _currentProfileName = null;
let _profilesLoaded = false;

async function loadProfilesTab() {
    _profilesLoaded = true;
    const loading = document.getElementById('profile-list-loading');
    const list = document.getElementById('profile-list');

    loading.style.display = 'block';
    list.style.display = 'none';
    list.innerHTML = '';

    try {
        const res = await fetch('/api/lxd/profiles');
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
                p.cpu ? `${p.cpu}c` : null,
                p.memory ? `${p.memory}G` : null,
                p.disk ? `${p.disk}G` : null,
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
        list.style.display = 'block';
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
    document.getElementById('profile-placeholder').style.display = 'none';
    document.getElementById('profile-edit-card').style.display = 'block';
    document.getElementById('profile-edit-name').textContent = name;
    document.getElementById('profile-alert').style.display = 'none';

    // Disable delete button for 'default'
    const deleteBtn = document.getElementById('profile-delete-btn');
    const isDefault = (name === 'default');
    deleteBtn.disabled = isDefault;
    deleteBtn.title = isDefault ? "Cannot delete the 'default' LXD profile" : "Delete this profile";
    deleteBtn.style.opacity = isDefault ? '0.5' : '1';
    deleteBtn.style.cursor = isDefault ? 'not-allowed' : 'pointer';

    // Fetch full profile details (includes cloud-init text)
    try {
        const res = await fetch(`/api/lxd/profiles/${encodeURIComponent(name)}`);
        const data = await res.json();
        if (!data.success) { showProfileAlert('danger', data.message); return; }
        const p = data.profile;
        document.getElementById('pe-description').value = p.description || '';
        document.getElementById('pe-cpu').value = p.cpu ?? '';
        document.getElementById('pe-memory').value = p.memory ?? '';
        document.getElementById('pe-disk').value = p.disk ?? '';
        document.getElementById('pe-cloud-init').value = p.cloud_init || '';
    } catch (err) {
        showProfileAlert('danger', `Failed to load profile: ${err.message}`);
    }
}

async function saveProfile() {
    if (!_currentProfileName) return;
    const payload = {
        description: document.getElementById('pe-description').value,
        cpu: parseInt(document.getElementById('pe-cpu').value) || null,
        memory: parseInt(document.getElementById('pe-memory').value) || null,
        disk: parseInt(document.getElementById('pe-disk').value) || null,
        cloud_init: document.getElementById('pe-cloud-init').value,
    };

    try {
        const res = await fetch(`/api/lxd/profiles/${encodeURIComponent(_currentProfileName)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (data.success) {
            showProfileAlert('success', `Profile '${_currentProfileName}' saved.`);
            loadProfilesTab();
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
        cpu: parseInt(document.getElementById('pn-cpu').value) || null,
        memory: parseInt(document.getElementById('pn-memory').value) || null,
        disk: parseInt(document.getElementById('pn-disk').value) || null,
        cloud_init: document.getElementById('pn-cloud-init').value,
    };

    try {
        const res = await fetch('/api/lxd/profiles', {
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
        const res = await fetch(`/api/lxd/profiles/${encodeURIComponent(_currentProfileName)}`, {
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
    document.getElementById('profile-new-card').style.display = 'block';
    document.getElementById('profile-edit-card').style.display = 'none';
    document.getElementById('profile-placeholder').style.display = 'none';
    document.getElementById('profile-alert').style.display = 'none';
    // Clear fields
    ['pn-name', 'pn-description', 'pn-cpu', 'pn-memory', 'pn-disk', 'pn-cloud-init']
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

async function loadDefaultCloudInit(targetId, templateType = 'container') {
    try {
        const res = await fetch(`/classrooms/cloud-init/template?template_type=${templateType}`);
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
