# Agent instructions

Read [docs/README.md](docs/README.md) for connection behavior and verification.

- Keep VRCFaceTracking and headset input local; the configurable address is the
  VTube Studio output destination.
- Preserve existing iFacialMocap behavior and settings compatibility.
- Keep runtime settings and authentication tokens out of Git.
- Follow the existing Python style in legacy files. Format new connection and
  UI tests with Ruff; avoid unrelated formatting changes.
- Run the verification commands in the docs before handing off changes.
