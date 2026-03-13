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

function loadCloudInitTemplate() {
    const cloudInitField = document.getElementById('cloud_init');
    const template = `#cloud-config
# Default user configuration
users:
  - name: ubuntu
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    ssh_authorized_keys:
      - ssh-rsa YOUR_PUBLIC_KEY_HERE

# Update packages on first boot
package_update: true
package_upgrade: false

# Install additional packages
packages:
  - vim
  - curl
  - wget

# Set hostname
hostname: my-vm

# Write files to the system
write_files:
  - path: /etc/motd
    content: |
      Welcome to this VM!
      Configured by cloud-init.

# Run commands on first boot
runcmd:
  - echo "Cloud-init completed successfully" >> /var/log/cloud-init-custom.log
`;
    cloudInitField.value = template;
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

    if (vmSuccess || vmError) {
        const vmTab = new bootstrap.Tab(document.getElementById('vm-settings-tab'));
        vmTab.show();
    } else if (passwordSuccess || passwordError) {
        const passwordTab = new bootstrap.Tab(document.getElementById('password-tab'));
        passwordTab.show();
    }
});
