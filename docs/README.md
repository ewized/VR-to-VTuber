# Development and connections

## VTube Studio on another PC

Run VR to VTuber, SteamVR, and VRCFaceTracking on the headset PC. Select
**VTube Studio** and enter the receiving PC's **IP address or hostname** before
pressing **Start**. Enter the API port separately; its default is `8001`.
`127.0.0.1` connects to the same PC. IPv4, IPv6, short computer names, and DNS
hostnames are accepted. Names must resolve from the headset PC.

On the receiving PC, enable VTube Studio's **Start API**, use the matching port,
and accept the plugin permission prompt. Allow inbound connections to that API
port through the receiving PC's firewall on the network used by both PCs.
VRCFaceTracking and SteamVR still run on the headset PC.
See the [VTube Studio API documentation](https://github.com/DenchiSoft/VTubeStudio#api-details)
for API activation, ports, and plugin authentication.

Do not enter `ws://`, a path, or a port in the address field. Leading and
trailing spaces are removed. Blank addresses and invalid ports show an error
and do not start the bridge. Stop the bridge before editing the address or port.
Both values are saved in `bridge_settings.json` as `vts_host` and `vts_port`.
Older settings files continue to use `127.0.0.1:8001` until changed.

The WebSocket client resolves hostnames when connecting. An unresolvable name
or unreachable receiver keeps the output waiting and retries the connection.
Changing PCs may require accepting a new VTube Studio permission prompt because
the existing authentication token is shared between destinations.

## Verification

Use Python 3.12 with Tk support. Install development dependencies:

```bash
python -m pip install -r requirements-dev.txt
```

Fast checks for the connection and form changes:

```bash
python -m unittest discover -s tests -p test_connections.py -v
python -m unittest discover -s tests -p test_ui.py -v
```

Complete automated checks:

```bash
python -m unittest discover -s tests -v
python -m ruff check .
python -m ruff format --check tests/test_connections.py tests/test_ui.py
```

The connection tests use local WebSocket receivers to check authentication and
tracking at a nondefault loopback address, a hostname with controlled DNS, and
IPv6. The UI tests open Tk windows and stub the tracking worker. Linux requires
a display, or `xvfb-run -a` before the test command. IPv6 is skipped if the OS
does not support IPv6 loopback. UI tests are skipped if a display is unavailable;
such a run does not verify the form. CI provides a display on Linux and Windows.

Ruff checks lint across the repository. Formatting checks cover the new test
files; existing production files retain their established style. Changes to the
test scope or formatter must preserve this distinction until a separate legacy
formatting change is authorized.

Hardware validation still requires Windows, SteamVR, a compatible headset,
VRCFaceTracking, and a receiving PC running VTube Studio. Automated receiver
tests do not verify those applications or the receiving PC's firewall.

## Windows executable

On Windows, run `build.bat` to produce `dist/VR to VTuber.exe`.
The **Build Windows executable** GitHub Actions workflow also builds on pushes
to `build/**` branches and supports manual dispatch. It runs the automated
checks, packages with the existing PyInstaller spec, and checks that the
executable stays running for five seconds. Download the
**VR-to-VTuber-Windows** artifact for the executable, SHA-256 checksum, source
commit, and installed package versions. This launch check does not verify
headset tracking or a connection to a real VTube Studio instance.
