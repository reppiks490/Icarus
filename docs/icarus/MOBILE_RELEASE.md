# ICARUS Mobile release path

ICARUS Mobile uses Expo Application Services (EAS) for signed iOS/Android builds. The repository pins EAS CLI 24.8.0 in the manual GitHub build workflow for reproducibility.

## One-time Expo account setup

This step requires the operator's Expo account and cannot be completed by repository code alone.

From the repository:

```bash
cd mobile
npx eas-cli@24.8.0 login
npx eas-cli@24.8.0 init
```

`eas init` links the app to an Expo project and writes the EAS project ID into app configuration. Commit that project ID; it is not a secret.

## GitHub authentication

Create a repository Actions secret named `EXPO_TOKEN` using a token from the Expo account that owns the linked project.

The workflow does not run on push or pull request. It can only be started manually from GitHub Actions.

## Build profiles

`mobile/eas.json` contains:

- `development`: development client/internal distribution.
- `preview`: internal distribution for device testing.
- `production`: store-oriented build with automatic build-number/version-code increment.

The manual workflow accepts `ios`, `android`, or `all` plus one of these profiles.

## Deliberate non-automation

This workflow triggers builds only. It does not auto-submit to TestFlight, App Store Connect, or Google Play. Store submission remains a separate explicit operator action because it can create external releases and depends on Apple/Google developer accounts, agreements, signing state, and review metadata.

## Private testing sequence

1. Link the EAS project once.
2. Add `EXPO_TOKEN` to GitHub Actions secrets.
3. Run **mobile-eas-build** with `platform=all`, `profile=preview`.
4. Install the generated internal-distribution build on physical devices.
5. Validate pairing, live snapshots, charts, matrix backtests, push registration, session rotation, and revocation against the hardened gateway.
6. Only after device validation, trigger a production profile.
