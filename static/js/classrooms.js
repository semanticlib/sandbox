// ============================================================
// Classroom Management
// ============================================================

let _currentClassroomId = null;
let _classroomsLoaded = false;

async function loadClassroomsTab() {
    _classroomsLoaded = true;
    const loading = document.getElementById('classroom-list-loading');
    const list = document.getElementById('classroom-list');

    loading.style.display = 'block';
    list.style.display = 'none';
    list.innerHTML = '';

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

            li.innerHTML = `
                <div>
                    <strong>${c.name}</strong>
                    <br><small class="text-muted">${typeIcon} ${c.image_type === 'virtual-machine' ? 'VM' : 'Container'}</small>
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

async function loadClassroomImages(context = 'edit') {
    const prefix = context === 'new' ? 'cn' : 'cc';
    const imageType = document.getElementById(`${prefix}-image-type`).value;
    const select = document.getElementById(`${prefix}-image-select`);

    select.innerHTML = '<option value="">— Select an image —</option>';
    select.disabled = true;

    // Reset cloud-init and image fields when type changes
    document.getElementById(`${prefix}-cloud-init`).value = '';
    document.getElementById(`${prefix}-image-description`).value = '';
    document.getElementById(`${prefix}-image-fingerprint`).value = '';
    document.getElementById(`${prefix}-image-alias`).value = '';

    // Toggle Load Default buttons visibility
    const containerBtn = document.getElementById(`${prefix}-load-container-default`);
    const vmBtn = document.getElementById(`${prefix}-load-vm-default`);
    if (containerBtn && vmBtn) {
        if (imageType === 'container') {
            containerBtn.style.display = 'inline-block';
            vmBtn.style.display = 'none';
        } else {
            containerBtn.style.display = 'none';
            vmBtn.style.display = 'inline-block';
        }
    }

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
        document.getElementById('cc-cloud-init').value = c.cloud_init || '';
        document.getElementById('cc-local-forwards').value = c.local_forwards || '';
        document.getElementById('cc-image-fingerprint').value = c.image_fingerprint || '';
        document.getElementById('cc-image-alias').value = c.image_alias || '';
        document.getElementById('cc-image-description').value = c.image_description || '';

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
        cloud_init: document.getElementById('cc-cloud-init').value || null,
        local_forwards: document.getElementById('cc-local-forwards').value || null,
        image_fingerprint: document.getElementById('cc-image-fingerprint').value || null,
        image_alias: document.getElementById('cc-image-alias').value || null,
        image_description: document.getElementById('cc-image-description').value || null,
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
        cloud_init: document.getElementById('cn-cloud-init').value || null,
        local_forwards: document.getElementById('cn-local-forwards').value || null,
        image_fingerprint: document.getElementById('cn-image-fingerprint').value || null,
        image_alias: document.getElementById('cn-image-alias').value || null,
        image_description: document.getElementById('cn-image-description').value || null,
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

// Modal for classroom deletion
let classroomToDelete = null;

function showDeleteClassroomModal() {
    if (!_currentClassroomId) return;

    classroomToDelete = _currentClassroomId;
    const classroomName = document.getElementById('classroom-edit-name').textContent;
    document.getElementById('deleteClassroomName').textContent = classroomName;

    const modal = new bootstrap.Modal(document.getElementById('deleteClassroomModal'));
    modal.show();

    // Set up confirm button handler
    document.getElementById('deleteClassroomConfirmBtn').onclick = async function() {
        modal.hide();
        await performDeleteClassroom();
    };
}

async function performDeleteClassroom() {
    if (!classroomToDelete) return;

    try {
        const res = await fetch(`/api/classrooms/${classroomToDelete}`, {
            method: 'DELETE'
        });
        const data = await res.json();
        if (data.success) {
            _currentClassroomId = null;
            classroomToDelete = null;
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

async function deleteClassroom() {
    showDeleteClassroomModal();
}

async function showNewClassroomForm() {
    document.getElementById('classroom-new-card').style.display = 'block';
    document.getElementById('classroom-edit-card').style.display = 'none';
    document.getElementById('classroom-placeholder').style.display = 'none';
    document.getElementById('classroom-alert').style.display = 'none';

    // Clear fields
    ['cn-name', 'cn-username', 'cn-image-description', 'cn-image-fingerprint', 'cn-image-alias', 'cn-cloud-init', 'cn-local-forwards']
        .forEach(id => { document.getElementById(id).value = ''; });

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
