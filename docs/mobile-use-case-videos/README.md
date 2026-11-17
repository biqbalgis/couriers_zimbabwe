# Mobile use-case recordings

Open `index.html` for the gallery. The timestamped recording directory contains one 390 × 844 WebM per UC01–UC26, poster screenshots, and a machine-readable manifest. Title cards describe the actual demonstration coverage. Synthetic scenario starting states are fixtures, not real custody evidence. No real SMS, payment or external disbursement is performed.

UC17 shows the proof/signature interface but does not save a native signature or complete delivery. UC24 is a clearly labelled native-only limitation walkthrough. Neither claims device acceptance. No Android device/emulator was attached during this recording.

Verification: all 26 files decode successfully and are 390 × 844; the local gallery lists 26 videos, and first/last playback passed. See the timestamped `validation.json` and `manifest.json` for file-level evidence. Mobile lint and TypeScript checks passed.

## Reproduce

Use the isolated API configuration in `mobile/tests/mobile_test_settings.py`. Migrate and run `seed_demo` with those settings, then serve port 8001. Temporarily configure the mobile web preview API as `http://localhost:8001/api` and run Expo web on port 8083. From `mobile`, run `node tests/record-use-cases.mjs`. The script creates fresh synthetic fixtures through `video_fixtures.py`, authenticates dedicated demo roles and records the actual mobile UI. It never targets the developer database. Restore the normal mobile API configuration afterward.

The test settings explicitly allow the `Idempotency-Key` CORS request header. Any separate browser-preview deployment must also allow that header; native requests are not governed by browser CORS.

Retake selected cases using `--output=<existing recording directory> --only=UC11,UC14`. This replaces only matching generated clips and updates the manifest/gallery. Existing desktop recordings under `docs/use-case-videos` are untouched. Failed takes are marked failed until successfully replaced; failure screenshots remain troubleshooting evidence.
