# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 2.x     | Yes       |
| < 2.0   | No        |

## Reporting a Vulnerability

**Email:** 64996768+mcp-tool-shop@users.noreply.github.com

**Response timeline:**

- Acknowledgement: within 48 hours
- Assessment + fix target: within 7 days
- Public disclosure: after fix is released

Please include:
- Description of the vulnerability
- Steps to reproduce
- Impact assessment

## Security & Data Scope

- **Data accessed:** Reads text input for TTS synthesis. Processes audio through configured backends (Kokoro, Piper, or mock). Returns PCM audio as numpy arrays or WAV files.
- **Data NOT accessed:** No network egress by default (backends are local). No telemetry, analytics, or tracking. No user data storage beyond transient audio buffers.
- **Permissions required:** Read access to TTS model files (Kokoro ONNX, Piper voices). Optional write access for audio output files.
