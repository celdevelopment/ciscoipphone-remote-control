# Cisco Phone Viewer 1.0.0 — Windows 11 x64

Offline per-user installation: extract the ZIP, scan it with your organization's
endpoint protection, run **Install.cmd**, then **Self Test.cmd**. No installed
Python, pip, administrator rights, or install-time downloads are needed.

Includes screen capture, Settings/Applications, navigation, keypad, and softkeys
for supported Cisco enterprise phones. HTTPS with certificate validation is the
default; `--allow-http` explicitly opts into unencrypted traffic.

Built and tested on a Windows GitHub runner. The release workflow gates publication
on source tests, lint, application static/dependency scans, archive checksums,
packaged-runtime tests, and provenance verification. See SECURITY-REVIEW.md and the
workflow logs for exact scope. Work-PC EDR and physical-phone validation remain
pending. Legacy bulk reset/certificate code and dependencies are excluded.

## Verify the signature

The ZIP has signed GitHub/Sigstore provenance. Verify with GitHub CLI:

```shell
gh attestation verify CiscoPhoneViewer-1.0.0-Windows11-x64.zip --repo celdevelopment/ciscoipphone-remote-control
```

A detached `.sigstore.json` bundle and SHA-256 checksum are also attached.
Provenance signing identifies the artifact's source and workflow; it does not add
Windows Authenticode publisher trust or remove Windows security warnings.
