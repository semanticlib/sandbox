from pylxd import Client


def get_lxd_client(server_url: str, verify_ssl: bool = True, cert=None, key=None):
    """
    Create LXD client using certificate authentication.
    
    Args:
        server_url: LXD server URL
        verify_ssl: Whether to verify SSL certificate
        cert: Client certificate PEM string
        key: Client private key PEM string
    
    Returns:
        pylxd.Client
    """
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
    
    return client
