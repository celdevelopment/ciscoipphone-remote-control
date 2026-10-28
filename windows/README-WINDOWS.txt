CISCO PHONE VIEWER 1.0.0 — WINDOWS 11 x64

INSTALL
1. Verify the ZIP SHA-256 against the separately supplied checksum.
2. Scan the ZIP/extracted folder with your organization's endpoint protection.
3. Extract the entire ZIP to a local folder. Do not launch from inside the ZIP.
4. Double-click Install.cmd. No administrator rights or downloads are required.
5. Open Cisco Phone Viewer from Start, or run Start Viewer.cmd in the installed
   folder at %LOCALAPPDATA%\Programs\CiscoPhoneViewer-1.0.0.

An official embedded Python runtime and pinned dependencies are included.
Nothing is added to PATH, installed system-wide, or registered as a service.
The installed files total approximately 40 MB. There is no automatic updater.
The installer refuses to overwrite an existing installation of this version.

USE
Enter the phone IP, CUCM end-user name, and password in the console. The password
is hidden. A browser opens the local viewer. Click Open Settings / Applications
for an 88xx, then use arrows, Select, digits, and softkeys. Close the console or
press Ctrl+C to stop the server; closing the browser alone does not stop it.

HTTPS is the default, with certificate validation. If your phone uses a private
CA, launch from a terminal with:
  "Start Viewer.cmd" --ca-file "C:\path\company-phone-ca.pem"

Only if your organization permits unencrypted phone management on a trusted LAN
or VPN, explicitly choose HTTP:
  "Start Viewer.cmd" --allow-http
HTTP can expose credentials, phone screen contents, and commands to network
observers. The program never silently falls back from HTTPS to HTTP. It never
turns off certificate validation. Certificate hostname/IP matching still applies.

Use the phone's IP address. Screenshots require Web Access, supported enterprise
phone firmware, a CUCM end user associated with the device, and a working CUCM
authentication URL. Phone Settings Access restrictions still apply. This app does
not alter those CUCM settings. It targets one phone, not a fleet. Key presses act
on the physical phone; changes you make within a phone menu have real effects.

SECURITY AND LIMITS
- Server listens only on 127.0.0.1. No inbound firewall rule is needed.
- Random per-run request token, Host/Origin checks, CSP nonces, and no caching.
- No stored passwords/screenshots, telemetry, external browser assets, or shell
  execution from menu commands. Input is constrained to an IP and known keys.
- Same-user local processes can access application memory/local browser content;
  this is not a defense against a compromised workstation.
- Signed upstream Python binaries are included, but this assembled ZIP and our
  CMD/Python application are not Authenticode-signed or enterprise certified.
  Do not bypass Windows/EDR blocks. Ask your IT team to review/approve the package.
- Static/dependency scanning is not a malware certification or penetration test.
  The GitHub release workflow checks Windows execution and signs provenance.
  Work-PC Defender/EDR checks and a physical phone test are still pending.
- Supports Windows 11 x64. ARM64 is not a native target of this package.

UNINSTALL
Stop the viewer. Delete %LOCALAPPDATA%\Programs\CiscoPhoneViewer-1.0.0 and
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Cisco Phone Viewer.cmd.
No phone credentials or user data files are created by this application.

See SECURITY-REVIEW.md and security-evidence for scope, findings, scan output,
component versions, and testing limitations. SHA256SUMS.json verifies file
integrity within the package; only the separately supplied ZIP hash verifies the
whole artifact against the copy supplied in this chat. Neither is a digital
signature.

GITHUB RELEASE SIGNATURE
Official releases from celdevelopment/ciscoipphone-remote-control carry detached
GitHub/Sigstore provenance signatures. With GitHub CLI installed, verify:
  gh attestation verify CiscoPhoneViewer-1.0.0-Windows11-x64.zip --repo celdevelopment/ciscoipphone-remote-control
This is artifact provenance signing, not Windows Authenticode publisher signing.
