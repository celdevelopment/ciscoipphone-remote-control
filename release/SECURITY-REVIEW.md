# Cisco Phone Viewer 1.0.0 — security review and Windows package

Review date: October 28, 2026. Target: Windows 11 x64, Cisco enterprise 88xx
firmware sip88xx.14-4-1-0301-6. Review performed on macOS; no physical phone was
contacted. This report is an engineering review, not a security certification.

## Disposition

Source review and automated application checks completed. The delivered ZIP is
prepared for Windows acceptance testing. Windows execution, Defender/enterprise
EDR scanning, corporate deployment approval, and a real-phone test remain pending.
Do not describe this package as malware-certified, signed, or Windows-tested.

## Checks and results

| Check | Result | Evidence |
|---|---|---|
| Bandit 1.9.4, repository Python sources excluding tests | 0 remaining findings | security-evidence/bandit-repository.json |
| Bandit, viewer + installed installer | 0 remaining findings | security-evidence/bandit-viewer.json |
| pip-audit 2.10.1 / PyPI advisory service, pinned app dependencies | 0 known vulnerabilities reported in Pillow 13.0.0 and DefusedXML 0.7.1 | security-evidence/viewer-dependency-audit.json |
| Unit/integration tests on macOS | 22 passed, including localhost HTTP requests, hostile XML, unsupported/large images, and installer integrity checks | security-evidence/macos-tests.txt |
| Ruff 0.4.3 and diff whitespace checks | Passed for changed Python files | Recorded during build |
| Mock browser test | Screenshot loaded and Settings button refreshed successfully under nonce CSP | security-evidence/mock-browser-check.jpg |
| High-confidence private-key/GitHub/AWS secret pattern check | 0 findings in app/packaging text sources | security-evidence/secret-pattern-review.json |
| Windows/runtime/physical phone test | Not run: no Windows execution environment or connected phone | Run Self Test.cmd on Windows, then test your device |
| Antivirus/Defender/EDR | Not run: no such scanner available on this Mac | Scan the transferred ZIP and extracted folder on the work PC |

Dependency auditing covers the two Python app distributions only; neither has
additional required runtime Python dependencies. It does not constitute a CVE
scan of every bundled native library or CPython component. Runtime and Pillow
native-library inventories are included for your organization's scanners.

## Findings addressed

- Unencrypted HTTP was the default. HTTPS is now the default, with certificate
  validation and optional --ca-file for a private CA. HTTP requires --allow-http;
  there is no silent downgrade or certificate-verification bypass.
- Untrusted XML used stdlib ElementTree parsing (Bandit B314). Parsing now uses
  DefusedXML, rejects DTDs/entities, and has a hostile-input regression test.
  The only suppressed Bandit check is B405 on the stdlib ElementTree import,
  which is used exclusively to construct outgoing XML. Parsing is not suppressed.
- Image decoding was broad, and Pillow versions were unpinned. Dependencies are
  now fixed to audited versions, decoding is restricted to PNG/JPEG/GIF/BMP,
  and screen dimensions are limited to 4 million pixels, in addition to an 8 MiB
  response limit. Decoder errors become readable UI errors.
- Local request resources were unbounded. The production server now admits at
  most eight simultaneous connections with a ten-second client read timeout;
  phone requests have an eight-second timeout. Phone requests are serialized.
- CSP allowed arbitrary inline scripts. The page now uses per-run CSP nonces,
  denies frames/forms/base changes, and keeps all assets local.
- Windows distribution now has checksum-verified upstream archives, a complete
  per-file integrity manifest, an installer that refuses missing/extra/modified
  files or symlinks, and no install-time dependency downloads.

Existing controls retained: bind only to 127.0.0.1; exact Host and Origin checks;
per-run API token; no CORS; no caching; hidden console password entry; credentials
remain server-side; fixed single-phone target and allowlisted keys; redirect and
proxy rejection; no disk persistence of passwords/screenshots; no analytics.

## Findings in the original bulk-control workflow (excluded from ZIP)

The original requirements.txt is not the viewer's dependency list. Its direct
pinned dependencies contain two distinct advisory identifiers (the PyPI service
returned duplicate records, four entries total):

- Dynaconf 3.2.5: PYSEC-2026-2147, unsafe Jinja resolver evaluation; advisory fixes
  include 3.2.13.
- lxml 5.1.0: PYSEC-2026-87, unsafe default XML entity resolution; advisory fixes
  include 6.1.0.

See security-evidence/legacy-direct-dependency-audit.json. Only direct requirements
were audited for this legacy inventory; the unpinned httpx requirement was
resolved to the current PyPI release for inventory. This is not a full legacy
transitive-dependency audit. Those legacy requirements were not upgraded as part
of the isolated viewer package; the older bulk tool still needs separate repair
and validation before use. Its HTTP transport and reset/certificate operations
are also outside this package. Do not install requirements.txt for the viewer.

## Package contents and provenance

Only the viewer, its installer/self-test, tests, documentation, runtime, and pinned
dependencies are shipped. No .env, phone CSV, Git metadata, databases, bulk reset
code, or certificate-erasure templates are included.

- CPython 3.14.10, official Windows x64 embeddable archive from python.org. Archive
  SHA-256 verified against the official Python release page. runtime/LICENSE.txt
  is retained. Upstream SBOM: security-evidence/python-runtime.spdx.json.
- Pillow 13.0.0 CPython 3.14 Windows x64 wheel and DefusedXML 0.7.1 universal wheel,
  downloaded from PyPI and verified against PyPI's published SHA-256 digests.
- COMPONENTS.json records source URLs and upstream archive digests. Each installed
  file is listed in SHA256SUMS.json. Licenses and Pillow's native-library SBOM are
  retained in their .dist-info directories.

The separate ZIP .sha256 file verifies the transferred artifact. The internal
manifest detects changed files; it is not a digital signature or independent
proof of publisher authenticity. Official runtime binaries retain upstream
signatures, but their Authenticode signatures were not validated on macOS. The application is not Authenticode-signed. GitHub release artifacts include
detached Sigstore provenance signatures, which do not add Windows publisher trust. Do not bypass SmartScreen or enterprise
security blocks; give IT this report and the package for review.

## Windows acceptance and uninstall

Verify the ZIP hash, scan with endpoint protection, extract everything, and run
Install.cmd as your normal user. It copies into
%LOCALAPPDATA%\Programs\CiscoPhoneViewer-1.0.0 and adds a Start Menu launcher.
No PATH modification, service, scheduled task, firewall exception, PowerShell
execution-policy change, or administrator permission is requested.

Run Self Test.cmd in the extracted/installed folder (17 viewer tests), then launch
Start Viewer.cmd and test the phone over HTTPS. Verify settings navigation and
screenshots with your CUCM-associated end user. All key presses act on the actual
phone, and configuration changes inside its menus have real effects. Local
same-user malicious processes are outside this application's security boundary.

To remove: stop the viewer, delete the installation folder, then delete
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Cisco Phone Viewer.cmd.

Upstream references:
- https://www.python.org/downloads/release/python-31410/
- https://pypi.org/project/Pillow/13.0.0/
- https://pypi.org/project/defusedxml/0.7.1/
- https://help.webex.com/article/nehgfoi/Troubleshooting-procedures


## GitHub release build validation

The release workflow rebuilds the ZIP from this source on a Windows runner. It
fails publication if source tests, lint, application scans, upstream checksum
checks, packaged-runtime tests, or provenance verification fail. Fresh scan logs
are included in security-evidence; the bundled-runtime self-test log is a release
asset. Refer to the workflow run for the actual Windows version and test results.
Statements above about Windows checks being pending describe the original Mac
review; a successful release workflow adds automated Windows runner validation.
Work-PC Defender/EDR and physical-phone testing still remain pending.

The ZIP is signed using GitHub/Sigstore provenance, with a detached verification
bundle attached to the release. This identifies the fork, source commit, workflow,
and artifact digest. It is not Authenticode, nor a security certification. Verify:

```shell
gh attestation verify CiscoPhoneViewer-1.0.0-Windows11-x64.zip --repo celdevelopment/ciscoipphone-remote-control
```
