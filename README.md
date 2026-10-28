# Cisco IP Phone remote control

### Description:

This app used for remotely delete ITL/CTL certificates and restarts the Cisco IP Phones sending to them keypress
execution command (CiscoIPPhoneExecute). For concurrency used asyncio. The results are writing to SQLite/PostgresSQL
database.

[Cisco IP Phone Programmobility Guide](https://www.cisco.com/c/en/us/td/docs/voice_ip_comm/cuipph/all_models/xsi/9-1-1/CUIP_BK_P82B3B16_00_phones-services-application-development-notes.html)


```shell
.
├── README.md
├── config
│   └── config.py
├── data
│   └── session_factory.py
├── db
│   ├── db_folder.py
│   └── phonedb.sqlite
├── models
│   └── model.py
├── service
│   ├── __init__.py
│   ├── client.py
│   └── service.py
├── settings.py
├── templates
│   └── keypress_templates.yaml
├── utils.py
├── phones.csv
├── requirements.txt
├── ruff.toml
├── .env
└── main.py
```

phones.csv - list of phones ip address <br>
templates/keypress_templates.yaml - phone templates with keypress <br>
.env.example - settings <br>
config/config.py - db config factory

### Requirements:

On CUCM cluster activate Cisco CTIManager services, it's required for remote control.
For remote control you need to create End User on CUCM with Standard CTI Enabled role and associate them with IP phones.

### Run PostgreSQL in Docker:

```shell
docker run --name db -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres:16-alpine3.19
```

### IP Phone Information Access:

> [!NOTE]
> Cisco Unified IP Phones have an embedded web server to provide a programming interface for external applications, and
> a debugging and management interface for system administrators.
> You can access the administrative pages using a standard web browser and pointing to the IP address of the phone
> with: http://phoneIP/, where phoneIP is the IP address of the specific phone.
> These device information pages are available in either HTML format for manual debugging purposes, or in XML format for
> automation purposes. The following table lists the available URLs and their purpose.
>
> | URL                                          | Description                                         | 
> |----------------------------------------------|-----------------------------------------------------|
> | /CGI/Execute (password-protected CGI script) | The target URL of a phone push (HTTP POST) request. |

> [!NOTE]
> Supported URIs by Phone Model. Detailed
> on [Cisco](https://www.cisco.com/c/en/us/td/docs/voice_ip_comm/cuipph/all_models/xsi/9-1-1/CUIP_BK_P82B3B16_00_phones-services-application-development-notes/CUIP_BK_P82B3B16_00_phones-services-application-development-notes_chapter_0101.html#CUIP_RF_S66EDF62_00)


### Remote screen viewer (88xx / supported enterprise phones)

The viewer runs separately from `main.py` and does not need a database or use the
bulk reset/certificate templates. It retrieves `/CGI/Screenshot`, displays the
current phone screen, and sends individual menu keys through `/CGI/Execute`.

```shell
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r viewer-requirements.txt
python remote_viewer.py --phone 192.0.2.10 --username phonecontrol
```

Replace the example IP and username with your phone IP and associated CUCM end
user. Enter the password at the hidden prompt. The browser opens a local viewer;
click **Open Settings / Applications** for 78xx/88xx, then navigate using arrows,
Select, the keypad, and Soft 1–4 (matching labels on the phone display). For older
79xx models, use the legacy Settings button. Opening the viewer only captures the
screen; it sends no key until you click a control. Key presses affect the physical
phone, including any configuration actions you choose in its menus.

Refresh manually or enable the two-second automatic refresh. Each key press is
followed by a fresh screenshot. This is a snapshot viewer, not a video stream.
Stop it with Ctrl+C in the terminal. Use `--no-browser` to print the viewer URL
without opening it. `PHONE_USERNAME` and `PHONE_PASSWORD` environment variables
are also supported; the viewer does not load `.env` or database settings.

Requirements and troubleshooting:

- Reach the phone IP from this computer (LAN/VPN), and enable phone Web Access
  through the appropriate CUCM configuration if it is currently disabled.
- Use a CUCM end user associated with the device. The phone must reach its CUCM
  authentication URL. HTTP 401/403 or Cisco XML errors can indicate authentication
  or device association problems.
- The phone model/firmware must implement `/CGI/Screenshot` and the requested key
  URIs. 88xx uses `Key:Applications`; actual support must be checked on the device.
  PNG, BMP, JPEG, and GIF screenshots are converted to PNG. Legacy XML screen
  formats are reported as unsupported rather than displayed as a blank image.
- CUCM Settings Access restrictions and phone configuration locks still apply.
- HTTPS with certificate verification is the default. Use `--ca-file` for a
  trusted private CA. Only use `--allow-http` if your organization permits
  unencrypted management traffic on a trusted network; it can expose credentials
  and screen contents. There is no automatic downgrade or certificate bypass.
- The viewer listens only on `127.0.0.1` on a random port, checks local request
  origins and a per-run token, and does not store credentials or screenshots.
  Credentials are sent only to the selected phone. There is no remote hosting mode.

Cisco references: [screen capture instructions](https://help.webex.com/article/nehgfoi/Troubleshooting-procedures)
and [supported key URIs](https://www.cisco.com/c/en/us/td/docs/voice_ip_comm/cuipph/all_models/xsi/9-1-1/CUIP_BK_P82B3B16_00_phones-services-application-development-notes/CUIP_BK_P82B3B16_00_phones-services-application-development-notes1_chapter_0101.html).

Run the viewer tests without a physical phone:

```shell
python -m unittest discover -s tests -v
```


### Windows 11 offline installer bundle

The `windows/` folder contains a per-user installer and checksum-pinned bundle
builder. The bundle includes the official CPython 3.14.10 x64 embeddable runtime,
Pillow 13.0.0, and DefusedXML 0.7.1. It requires no preinstalled Python, pip,
administrator rights, PowerShell policy changes, or install-time downloads.

Extract the delivered ZIP, run `Install.cmd`, then open **Cisco Phone Viewer**
from Start. `Self Test.cmd` tests the bundled runtime and viewer locally without
contacting a phone. Read `README-WINDOWS.txt` and `SECURITY-REVIEW.md` before use.
GitHub releases include signed Sigstore provenance and automated Windows-runner
validation. This is not Windows Authenticode signing; enterprise approval, work-PC
EDR validation, and a real-device test are still needed for your environment.

`windows/build_bundle.py --help` lists the offline inputs needed to rebuild the
bundle. Only viewer files are included: the bulk reset/certificate code, its
legacy dependencies, `.env`, phone lists, and database files are excluded.


Download the Windows viewer from the fork's [releases](https://github.com/celdevelopment/ciscoipphone-remote-control/releases).
Verify its signed provenance with:

```shell
gh attestation verify CiscoPhoneViewer-1.0.0-Windows11-x64.zip --repo celdevelopment/ciscoipphone-remote-control
```

The manually dispatched `.github/workflows/release-windows.yml` rebuilds the
package on Windows, runs source and packaged-runtime tests, performs application
security scans, signs provenance, verifies it, and publishes the release.
