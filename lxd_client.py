from pylxd import Client


def get_lxd_client(server_url: str = None, use_socket: bool = False, verify_ssl: bool = True, cert=None, key=None):
    """
    Create LXD client using certificate authentication or Unix socket.
    
    Args:
        server_url: LXD server URL (used when use_socket is False)
        use_socket: Whether to use Unix socket connection (local LXD)
        verify_ssl: Whether to verify SSL certificate
        cert: Client certificate PEM string
        key: Client private key PEM string
    
    Returns:
        pylxd.Client
    """
    # Use Unix socket for local LXD - just call Client() with no args
    if use_socket:
        # Client() automatically connects to /var/lib/lxd/unix.socket
        # Certificates can still be provided if LXD requires authentication
        if cert and key:
            client = Client(
                cert=(cert, key),
                verify=verify_ssl
            )
        else:
            client = Client()
    elif server_url:
        # Use HTTPS connection with server URL
        if cert and key:
            client = Client(
                endpoint=server_url,
                cert=(cert, key),
                verify=verify_ssl
            )
        else:
            client = Client(
                endpoint=server_url,
                verify=verify_ssl
            )
    else:
        # Default to local socket
        client = Client()
    
    return client
