import os
import json
import base64
from pathlib import Path
from typing import Optional
from loguru import logger

# Try to use cryptography, otherwise fallback to custom obfuscation
try:
    from cryptography.fernet import Fernet
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

# Try to import keyring for Windows Credential Manager integration
try:
    import keyring
    HAS_KEYRING = True
except ImportError:
    HAS_KEYRING = False

class CredentialVault:
    """Manages secure key and token storage, integrating Windows Credential Manager and local encryption."""
    
    def __init__(self, vault_dir: str = "data/security"):
        self.vault_path = Path(vault_dir) / "vault.bin"
        self.key_path = Path(vault_dir) / "vault.key"
        self.vault_path.parent.mkdir(parents=True, exist_ok=True)
        self._encryption_key = self._get_or_create_key()
        
    def _get_or_create_key(self) -> bytes:
        """Load or generate a master encryption key."""
        if self.key_path.exists():
            with open(self.key_path, "rb") as f:
                return f.read()
        else:
            if HAS_CRYPTOGRAPHY:
                key = Fernet.generate_key()
            else:
                key = base64.b64encode(os.urandom(32))
            
            with open(self.key_path, "wb") as f:
                f.write(key)
            try:
                os.chmod(self.key_path, 0o600)
            except Exception:
                pass
            return key
            
    def _encrypt(self, plaintext: str) -> str:
        if HAS_CRYPTOGRAPHY:
            f = Fernet(self._encryption_key)
            return f.encrypt(plaintext.encode()).decode()
        else:
            key_cycle = self._encryption_key * (len(plaintext) // len(self._encryption_key) + 1)
            xor_bytes = bytes(a ^ b for a, b in zip(plaintext.encode(), key_cycle))
            return base64.b64encode(xor_bytes).decode()
            
    def _decrypt(self, ciphertext: str) -> str:
        if HAS_CRYPTOGRAPHY:
            f = Fernet(self._encryption_key)
            return f.decrypt(ciphertext.encode()).decode()
        else:
            xor_bytes = base64.b64decode(ciphertext.encode())
            key_cycle = self._encryption_key * (len(xor_bytes) // len(self._encryption_key) + 1)
            return bytes(a ^ b for a, b in zip(xor_bytes, key_cycle)).decode()

    def store_credential(self, service: str, username: str, secret: str) -> bool:
        """Store a secret securely."""
        if HAS_KEYRING:
            try:
                keyring.set_password(service, username, secret)
                logger.info(f"Stored credential for '{service}' in Windows Credential Manager")
                return True
            except Exception as e:
                logger.warning(f"Windows Credential Manager failed: {e}. Falling back to encrypted file.")
                
        try:
            vault_data = {}
            if self.vault_path.exists():
                with open(self.vault_path, "r") as f:
                    encrypted_content = f.read()
                    if encrypted_content:
                        decrypted_data = self._decrypt(encrypted_content)
                        vault_data = json.loads(decrypted_data)
                        
            vault_data[f"{service}:{username}"] = secret
            encrypted_str = self._encrypt(json.dumps(vault_data))
            with open(self.vault_path, "w") as f:
                f.write(encrypted_str)
            logger.info(f"Stored credential for '{service}' in local vault")
            return True
        except Exception as e:
            logger.error(f"Failed to write credential in encrypted vault: {e}")
            return False
            
    def get_credential(self, service: str, username: str) -> Optional[str]:
        """Retrieve a credential."""
        if HAS_KEYRING:
            try:
                password = keyring.get_password(service, username)
                if password:
                    return password
            except Exception as e:
                logger.warning(f"Keyring retrieval failed: {e}")
                
        if self.vault_path.exists():
            try:
                with open(self.vault_path, "r") as f:
                    encrypted_content = f.read()
                if encrypted_content:
                    decrypted_data = self._decrypt(encrypted_content)
                    vault_data = json.loads(decrypted_data)
                    return vault_data.get(f"{service}:{username}")
            except Exception as e:
                logger.error(f"Failed to read local encrypted vault: {e}")
                
        return None
