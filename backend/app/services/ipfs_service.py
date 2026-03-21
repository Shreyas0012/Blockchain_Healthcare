"""IPFS Service - Encrypt and upload medical records to IPFS via Pinata."""
import os
import hashlib
import json
import requests
from datetime import datetime
from app.services.encryption import encryption_service


class IPFSService:
    def __init__(self):
        self.pinata_api_key = os.getenv("PINATA_API_KEY", "")
        self.pinata_secret = os.getenv("PINATA_SECRET_KEY", "")
        self.gateway = "https://gateway.pinata.cloud/ipfs/"

    def _generate_simulated_cid(self, data: bytes) -> str:
        """Generate a realistic-looking IPFS CID for demo/simulation."""
        h = hashlib.sha256(data).hexdigest()
        return f"Qm{h[:44]}"

    def upload_record(self, file_bytes: bytes, metadata: dict) -> dict:
        """Encrypt file + metadata bundle and upload to IPFS."""
        bundle = {
            "metadata": metadata,
            "timestamp": datetime.utcnow().isoformat(),
            "file_size": len(file_bytes),
            "file_hash": hashlib.sha256(file_bytes).hexdigest()
        }
        bundle_json = json.dumps(bundle).encode("utf-8")

        # Encrypt both the file and the metadata
        encrypted_file = encryption_service.encrypt(file_bytes)
        encrypted_meta = encryption_service.encrypt(bundle_json)

        combined = encrypted_file + b"|||SEPARATOR|||" + encrypted_meta

        # Try real Pinata upload, fall back to simulation
        if self.pinata_api_key and self.pinata_secret:
            try:
                cid = self._pinata_upload(combined, metadata.get("patient", "unknown"))
                return {"cid": cid, "gateway_url": f"{self.gateway}{cid}", "encrypted": True, "simulated": False}
            except Exception as e:
                print(f"[IPFS] Pinata upload failed, using simulation: {e}")

        cid = self._generate_simulated_cid(combined)
        return {"cid": cid, "gateway_url": f"{self.gateway}{cid}", "encrypted": True, "simulated": True}

    def _pinata_upload(self, data: bytes, name: str) -> str:
        url = "https://api.pinata.cloud/pinning/pinFileToIPFS"
        headers = {
            "pinata_api_key": self.pinata_api_key,
            "pinata_secret_api_key": self.pinata_secret
        }
        files = {"file": (f"{name}_record.enc", data)}
        resp = requests.post(url, headers=headers, files=files, timeout=30)
        resp.raise_for_status()
        return resp.json()["IpfsHash"]

    def verify_integrity(self, original_hash: str, file_bytes: bytes) -> bool:
        """Verify a file's integrity against its stored hash."""
        current_hash = hashlib.sha256(file_bytes).hexdigest()
        return current_hash == original_hash

    def download_record(self, cid: str) -> dict:
        """Download and decrypt a record from IPFS."""
        if not cid or cid.startswith("sim_"):
            return {"error": "Invalid or simulated CID"}

        try:
            # 1. Download from Pinata Gateway
            url = f"{self.gateway}{cid}"
            print(f"[IPFS] Downloading from Gateway: {url}")
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            combined = resp.content

            # 2. Split by separator
            parts = combined.split(b"|||SEPARATOR|||")
            if len(parts) < 2:
                # If no separator, the record might be old/unencrypted or just a single file
                return {"error": "Malformed encrypted record"}

            encrypted_file = parts[0]
            encrypted_meta = parts[1]

            # 3. Decrypt
            decrypted_meta_json = encryption_service.decrypt(encrypted_meta).decode("utf-8")
            metadata = json.loads(decrypted_meta_json)
            
            # Note: We don't decrypt the file here unless requested, 
            # as most dashboard data is in the metadata dict (vitals).
            return metadata.get("metadata", {})
        except Exception as e:
            print(f"[IPFS] Download/Decrypt failed for {cid}: {e}")
            return {"error": str(e)}


ipfs_service = IPFSService()
