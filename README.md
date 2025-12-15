# OneWayQR (Python)

Simple MVP for sending files/logs/binary data over QR code sequences with optional multi-QR grid, XOR parity, and integrity checks.

## Quick Start
- Install deps: `pip install -e .` (and `pip install reedsolo` if you later add stronger FEC). CLI entrypoint: `onewayqr` (alias `qrc`).
- Send (window display): `onewayqr send /path/to/file --grid-rows 2 --grid-cols 2 --fps 10`
- Send to MP4 (no window): `onewayqr send /path/to/dir --compress --no-display --video-output out.mp4`
- Receive from camera: `onewayqr receive --extract --output out_dir`
- Receive from video: `onewayqr receive --input out.mp4 --extract --output out_dir`

## Notes
- Payloads: files are sent raw; directories are packed as tar (optionally gz). `--compress` gzips payloads (base64 + QR ECC already applied).
- Framing: custom header + CRC32, session header repeats, data blocks grouped in superblocks with XOR parity (recovers one missing block per superblock).
- Capacity tuning: default chunk size is conservative (512 bytes before base64). Adjust `--chunk-size`, `--grid-rows/cols`, `--fps` per hardware; smaller chunks improve robustness.
- QR generation: `segno` (ECC level H), composed to a fixed grid; OpenCV window renders frames and optionally writes MP4.
- Decode: OpenCV `detectAndDecodeMulti` on camera/video; base64 -> frame parser -> reassembly; SHA256 of payload verified before extract.

## Legal & Compliance Notice
- Intended Use: lawful, research, educational, and operational scenarios where one-way/offline transfer is permitted and compliant with local regulations.
- Non-Intended / Prohibited Use: any illegal, malicious, privacy-invasive, or rights-infringing activity; deployment in jurisdictions or contexts that violate applicable law or policy.
- No Warranty & No Liability: provided “AS IS” without warranties; maintainers are not liable for damages or misuse by third parties.
- Governance: by using this project you agree to ensure your own compliance (security, privacy, export, and sector-specific rules).

## Limitations / Next Steps
- FEC is basic XOR parity; integrate Reed-Solomon for multi-loss recovery.
- No adaptive exposure/layout detection; assumes stable lighting and framing.
- No resumable sessions; playback is one-shot per run.
- Base64 adds ~33% overhead; keep chunk size modest to fit QR version for your display/camera combo.

## 中文版
中文版 README 位于 `README.zh.md`，请在修改英文版时同步更新中文内容。*** End Patchриста to=functions.apply_patch ***!
