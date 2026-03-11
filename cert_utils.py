from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
from cryptography import x509
from cryptography.x509.oid import NameOID
from datetime import datetime, timedelta


def generate_client_certificate(client_name: str = "fastapi-client", validity_days: int = 3650):
    """
    Generate a client certificate and private key for LXD authentication.
    
    Args:
        client_name: Name for the certificate (shown in LXD trust list)
        validity_days: Certificate validity period (default 10 years)
    
    Returns:
        tuple: (certificate_pem, private_key_pem)
    """
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    
    # Generate certificate
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, client_name),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "LXD Client"),
    ])
    
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow())
        .not_valid_after(datetime.utcnow() + timedelta(days=validity_days))
        .add_extension(
            x509.ExtendedKeyUsage([
                x509.OID_CLIENT_AUTH,
            ]),
            critical=True,
        )
        .sign(private_key, hashes.SHA256(), default_backend())
    )
    
    # Serialize certificate
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode('utf-8')
    
    # Serialize private key
    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')
    
    return cert_pem, key_pem
