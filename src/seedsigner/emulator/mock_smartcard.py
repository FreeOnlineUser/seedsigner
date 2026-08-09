"""
Mock Smartcard Emulation for SeedSigner Emulator

Provides a simulated Satochip/Seedkeeper smartcard for testing
the smartcard integration without physical hardware.

Features:
- Simulated card with configurable seed storage
- PIN verification
- Secure channel simulation
- Seedkeeper secret storage
"""

import hashlib
import os
from typing import Optional, List, Dict, Any


# Simulated card state
class MockCardState:
    """Persistent state for the mock smartcard"""

    def __init__(self):
        self.is_initialized = True
        self.pin = [0x31, 0x32, 0x33, 0x34, 0x35, 0x36]  # Default PIN: "123456"
        self.pin_tries_remaining = 3
        self.is_unlocked = False
        self.label = "Emulated Satochip"
        self.card_type = "satochip"  # or "seedkeeper", "satodime"

        # Generate a consistent UID based on emulator
        self.uid = bytes.fromhex("0102030405060708")
        self.uid_sha1 = hashlib.sha1(self.uid).hexdigest()[:8].upper()

        # Seedkeeper storage
        self.secrets: Dict[int, Dict[str, Any]] = {}
        self.next_secret_id = 1
        self.total_memory = 32768
        self.used_memory = 0

        # Stored seed (for Satochip mode)
        self.stored_seed: Optional[bytes] = None
        self.stored_seed_fingerprint: Optional[str] = None

    def reset(self):
        """Reset card to factory state"""
        self.__init__()


# Global card state
_card_state = MockCardState()


class MockCardConnector:
    """
    Mock implementation of pysatochip.CardConnector

    Simulates a Satochip/Seedkeeper smartcard for emulator testing.
    """

    def __init__(self, card_filter=None, debug=False):
        self.card_filter = card_filter or ["satochip", "seedkeeper", "satodime"]
        self.debug = debug
        self.state = _card_state

        # Card info
        self.UID_SHA1 = self.state.uid_sha1
        self.card_type = self.state.card_type
        self.needs_secure_channel = False
        self.is_seeded = self.state.stored_seed is not None

        print(f"[MockCard] CardConnector created (filter={card_filter})")
        print(f"[MockCard] Card UID: {self.UID_SHA1}")

    def card_get_status(self):
        """Get card status - returns (response, sw1, sw2, status_dict)"""
        status = {
            "protocol_major_version": 0,
            "protocol_minor_version": 12,
            "applet_major_version": 0,
            "applet_minor_version": 12,
            "is_seeded": self.state.stored_seed is not None,
            "setup_done": self.state.is_initialized,
            "pin_tries_remaining": self.state.pin_tries_remaining,
            "needs_secure_channel": False,
            "free_memory": self.state.total_memory - self.state.used_memory,
        }
        print(f"[MockCard] card_get_status: {status}")
        return (bytes(32), 0x90, 0x00, status)

    def card_get_label(self):
        """Get card label"""
        print(f"[MockCard] card_get_label: {self.state.label}")
        return self.state.label

    def card_set_label(self, label: str):
        """Set card label"""
        self.state.label = label
        print(f"[MockCard] card_set_label: {label}")
        return (0x90, 0x00)

    def card_verify_PIN(self, pin: List[int]):
        """Verify PIN"""
        print(f"[MockCard] card_verify_PIN called")
        if pin == self.state.pin:
            self.state.is_unlocked = True
            self.state.pin_tries_remaining = 3
            print("[MockCard] PIN verified successfully")
            return (bytes([self.state.pin_tries_remaining]), 0x90, 0x00)
        else:
            self.state.pin_tries_remaining -= 1
            print(f"[MockCard] PIN incorrect, {self.state.pin_tries_remaining} tries remaining")
            if self.state.pin_tries_remaining <= 0:
                return (bytes([0]), 0x63, 0xC0)  # Card blocked
            return (bytes([self.state.pin_tries_remaining]), 0x63, 0xC0 | self.state.pin_tries_remaining)

    def card_change_PIN(self, old_pin: List[int], new_pin: List[int]):
        """Change PIN"""
        if old_pin == self.state.pin:
            self.state.pin = new_pin
            print("[MockCard] PIN changed successfully")
            return (0x90, 0x00)
        return (0x63, 0xC0)

    def card_initiate_secure_channel(self):
        """Initiate secure channel (mock - just succeeds)"""
        print("[MockCard] Secure channel initiated")
        self.needs_secure_channel = False
        return True

    def card_disconnect(self):
        """Disconnect from card"""
        print("[MockCard] Card disconnected")
        self.state.is_unlocked = False

    # Satochip seed operations
    def card_bip32_import_seed(self, seed: bytes):
        """Import BIP32 seed to card"""
        self.state.stored_seed = seed
        # Calculate fingerprint
        from embit import bip32
        root = bip32.HDKey.from_seed(seed)
        self.state.stored_seed_fingerprint = root.derive("m/0").fingerprint.hex()
        self.is_seeded = True
        print(f"[MockCard] Seed imported, fingerprint: {self.state.stored_seed_fingerprint}")
        return (0x90, 0x00)

    def card_bip32_get_xpub(self, path: str, xtype: str = "standard"):
        """Get xpub for derivation path"""
        if not self.state.stored_seed:
            print("[MockCard] No seed stored")
            return (None, 0x69, 0x85)  # Conditions not satisfied

        from embit import bip32
        root = bip32.HDKey.from_seed(self.state.stored_seed)
        derived = root.derive(path)
        xpub = derived.to_public().to_base58()
        print(f"[MockCard] Generated xpub for {path}: {xpub[:20]}...")
        return (xpub, 0x90, 0x00)

    def card_sign_message(self, message: bytes, path: str):
        """Sign a message"""
        if not self.state.stored_seed:
            return (None, 0x69, 0x85)

        from embit import bip32, ec
        root = bip32.HDKey.from_seed(self.state.stored_seed)
        key = root.derive(path)
        # Create signature (simplified - real implementation uses specific signing)
        msg_hash = hashlib.sha256(message).digest()
        sig = key.key.sign(msg_hash)
        print(f"[MockCard] Signed message with {path}")
        return (sig.serialize(), 0x90, 0x00)

    def card_sign_transaction_hash(self, tx_hash: bytes, path: str):
        """Sign a transaction hash"""
        if not self.state.stored_seed:
            return (None, 0x69, 0x85)

        from embit import bip32
        root = bip32.HDKey.from_seed(self.state.stored_seed)
        key = root.derive(path)
        sig = key.key.sign(tx_hash)
        print(f"[MockCard] Signed tx hash with {path}")
        return (sig.serialize(), 0x90, 0x00)

    # Seedkeeper operations
    def seedkeeper_get_status(self):
        """Get Seedkeeper status"""
        status = {
            "free_memory": self.state.total_memory - self.state.used_memory,
            "total_memory": self.state.total_memory,
            "num_secrets": len(self.state.secrets),
        }
        print(f"[MockCard] seedkeeper_get_status: {status}")
        return (bytes(16), 0x90, 0x00, status)

    def seedkeeper_list_secret_headers(self):
        """List all secret headers"""
        headers = []
        for sid, secret in self.state.secrets.items():
            headers.append({
                "id": sid,
                "type": secret.get("type", 0x10),
                "origin": secret.get("origin", 0x01),
                "export_rights": secret.get("export_rights", 0x01),
                "label": secret.get("label", f"Secret {sid}"),
            })
        print(f"[MockCard] Listed {len(headers)} secrets")
        return headers

    def seedkeeper_import_secret(self, secret_dic: dict):
        """Import a secret to Seedkeeper"""
        sid = self.state.next_secret_id
        self.state.next_secret_id += 1

        # Calculate storage size
        secret_size = len(secret_dic.get("secret_list", []))
        padded_size = ((secret_size + 15) // 16) * 16 + 16  # AES padding

        self.state.secrets[sid] = {
            "type": secret_dic.get("type", 0x10),
            "origin": secret_dic.get("origin", 0x01),
            "export_rights": secret_dic.get("export_rights", 0x01),
            "label": secret_dic.get("label", f"Secret {sid}"),
            "secret_list": secret_dic.get("secret_list", []),
        }
        self.state.used_memory += padded_size

        print(f"[MockCard] Imported secret {sid}, used {padded_size} bytes")
        return {"id": sid, "fingerprint": hashlib.sha256(bytes(secret_dic.get("secret_list", []))).hexdigest()[:8]}

    def seedkeeper_export_secret(self, sid: int, export_rights: int = 0x01):
        """Export a secret from Seedkeeper"""
        if sid not in self.state.secrets:
            print(f"[MockCard] Secret {sid} not found")
            return (None, 0x69, 0x85)

        secret = self.state.secrets[sid]
        print(f"[MockCard] Exported secret {sid}")
        return (secret, 0x90, 0x00)

    def seedkeeper_reset_secret(self, sid: int):
        """Delete a secret from Seedkeeper"""
        if sid in self.state.secrets:
            del self.state.secrets[sid]
            print(f"[MockCard] Deleted secret {sid}")
            return (0x90, 0x00)
        return (0x69, 0x85)


class MockJCconstants:
    """Mock JCconstants from pysatochip"""
    # Card types
    SATOCHIP = 0x00
    SEEDKEEPER = 0x01
    SATODIME = 0x02


# Exception classes that pysatochip uses
class UnexpectedSW12Error(Exception):
    """Raised when card returns unexpected status words"""
    pass

class IdentityBlockedError(Exception):
    """Raised when card identity is blocked"""
    pass

class WrongPinError(Exception):
    """Raised when PIN is incorrect"""
    pass

class CardResetToFactoryError(Exception):
    """Raised when card is reset to factory"""
    pass


# BIP39 wordlist dictionary (mock)
BIP39_WORDLIST_DIC = {
    "en": "english",
    "jp": "japanese",
    "es": "spanish",
    "zh": "chinese_simplified",
    "fr": "french",
}

# Seedkeeper dictionaries
SEEDKEEPER_DIC_TYPE = {
    0x10: "BIP39 Mnemonic",
    0x20: "Electrum Mnemonic",
    0x30: "Master Seed",
    0x40: "Private Key",
    0x50: "Public Key",
    0x70: "Password",
    0x80: "Master Password",
    0x90: "Certificate",
    0xA0: "2FA Secret",
    0xB0: "Free Text",
    0xC0: "Wallet Descriptor",
}

SEEDKEEPER_DIC_ORIGIN = {
    0x01: "Imported - Plain",
    0x02: "Imported - Encrypted",
    0x03: "Generated Oncard",
}

SEEDKEEPER_DIC_EXPORT_RIGHTS = {
    0x00: "Export Forbidden",
    0x01: "Export in Plaintext Allowed",
    0x02: "Export Encrypted Only",
    0x03: "Export Authenticated Only",
}


# Utility functions that pysatochip.util provides
def dict_swap_keys_values(d):
    """Swap keys and values in a dictionary"""
    return {v: k for k, v in d.items()}


# Export mock classes
def get_mock_modules():
    """Return dict of mock modules to inject into sys.modules"""
    import sys

    # Create mock pysatochip module
    mock_pysatochip = type(sys)('pysatochip')

    # CardConnector submodule
    mock_cc = type(sys)('pysatochip.CardConnector')
    mock_cc.CardConnector = MockCardConnector
    mock_cc.UnexpectedSW12Error = UnexpectedSW12Error
    mock_cc.IdentityBlockedError = IdentityBlockedError
    mock_cc.WrongPinError = WrongPinError
    mock_cc.CardResetToFactoryError = CardResetToFactoryError
    mock_pysatochip.CardConnector = mock_cc

    # JCconstants submodule
    mock_jc = type(sys)('pysatochip.JCconstants')
    mock_jc.JCconstants = MockJCconstants
    mock_jc.SEEDKEEPER_DIC_TYPE = SEEDKEEPER_DIC_TYPE
    mock_jc.SEEDKEEPER_DIC_ORIGIN = SEEDKEEPER_DIC_ORIGIN
    mock_jc.SEEDKEEPER_DIC_EXPORT_RIGHTS = SEEDKEEPER_DIC_EXPORT_RIGHTS
    mock_jc.BIP39_WORDLIST_DIC = BIP39_WORDLIST_DIC
    mock_pysatochip.JCconstants = mock_jc

    # util submodule
    mock_util = type(sys)('pysatochip.util')
    mock_util.dict_swap_keys_values = dict_swap_keys_values
    mock_pysatochip.util = mock_util

    # Create mock pyscard module (just needs to exist)
    mock_pyscard = type(sys)('smartcard')
    mock_pyscard.System = type(sys)('smartcard.System')
    mock_pyscard.System.readers = lambda: ["Mock Reader 0"]  # Pretend we have a reader

    return {
        'pysatochip': mock_pysatochip,
        'pysatochip.CardConnector': mock_cc,
        'pysatochip.JCconstants': mock_jc,
        'pysatochip.util': mock_util,
        'smartcard': mock_pyscard,
        'smartcard.System': mock_pyscard.System,
    }


def install_mock_smartcard():
    """Install mock smartcard modules into sys.modules"""
    import sys
    for name, module in get_mock_modules().items():
        sys.modules[name] = module
    print("[Emulator] Mock smartcard installed")


def reset_card():
    """Reset the mock card to factory state"""
    global _card_state
    _card_state.reset()
    print("[MockCard] Card reset to factory state")


def set_card_type(card_type: str):
    """Set the type of card to emulate: 'satochip', 'seedkeeper', or 'satodime'"""
    global _card_state
    _card_state.card_type = card_type
    print(f"[MockCard] Card type set to: {card_type}")


def preload_seed(mnemonic: str):
    """Preload a seed into the mock card for testing"""
    from embit import bip39, bip32
    seed = bip39.mnemonic_to_seed(mnemonic)
    _card_state.stored_seed = seed
    root = bip32.HDKey.from_seed(seed)
    _card_state.stored_seed_fingerprint = root.derive("m/0").fingerprint.hex()
    print(f"[MockCard] Preloaded seed with fingerprint: {_card_state.stored_seed_fingerprint}")
