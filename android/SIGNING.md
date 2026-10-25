# Android signing and upgrade continuity

**Current warning:** GitHub-hosted runner debug keystores are regenerated. APKs
with different signing certificates cannot install over each other, even if
they have the same `applicationId`. V15 and the first V16 artifacts were
confirmed to have different signing certificates. Uninstalling an APK removes
local app data because backup is intentionally disabled.

## Stable signing (one-time user configuration)

1. Generate and securely retain a new Android signing keystore yourself using
   Android Studio or `keytool`. **Keep the private keystore and passwords
   outside the Git repository** and preferably store an offline backup.
2. In the private GitHub repo, open **Settings → Secrets and variables → Actions**.
   Create these repository secrets:
   - `BTC_PAPER_SIGNING_KEYSTORE_B64`: base64 encoding of the keystore bytes,
     without line breaks
   - `BTC_PAPER_SIGNING_STORE_PASSWORD`: keystore password
   - `BTC_PAPER_SIGNING_KEY_ALIAS`: key alias
   - `BTC_PAPER_SIGNING_KEY_PASSWORD`: key password
3. Re-run the Android APK workflow. The pipeline will decode the keystore
   in the runner's private temporary directory and use it for debug APK signing.
   The key is never committed or uploaded with the APK.

**Important:** The first stable-signed APK still cannot update any prior APK
signed with a different certificate. Uninstall the old debug app once before
installing the stable-signed build. After that, keep using the same signing
key for in-place upgrades. Backing up the key is essential.

This workflow is for a paper-trading prototype. A public production app with
money or sensitive user data needs a separate secured release-signing process,
formal testing and independent security review.
