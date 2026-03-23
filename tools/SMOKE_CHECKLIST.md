# Midas Smoke Checklist

## Server

```bash
cd server
.venv/bin/python tools/selfcheck.py
.venv/bin/python tools/smoke_test.py --base-url http://127.0.0.1:8000 --profile web_guard
```

Checks:
- `GET /health`
- `POST /api/bilibili/summarize` invalid-input guard
- `POST /api/xiaohongshu/summarize-url` invalid-input guard in `web_guard`

## Android

```bash
cd android
./gradlew :app:testDebugUnitTest
```

Checks:
- Compose smoke tests
- repository / mapper unit tests

## Release Artifact

```bash
tools/release.sh
```

Verify:
- exported APK absolute path
- exported APK timestamp
- exported APK SHA256
- latest alias path and SHA256
- candidate APK stats printed before selection
