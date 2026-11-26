<div align="center">

<img width="1345" height="247" alt="QuickeR" src="https://github.com/user-attachments/assets/f661f708-ef80-4ae7-8e3b-78a397f6af3c" />

### Create QRs quicker, without accounts, limits, ads, purchases or tracking.

[![Latest release](https://img.shields.io/github/v/release/ChoiceZero/QuickeR?style=for-the-badge&labelColor=101418&color=a6d1a0&label=release)](https://github.com/ChoiceZero/QuickeR/releases/latest)
[![GitHub last commit](https://img.shields.io/github/last-commit/ChoiceZero/QuickeR?style=for-the-badge&labelColor=101418&color=9ccbfb)](https://github.com/ChoiceZero/QuickeR/commits)
[![GitHub Repo stars](https://img.shields.io/github/stars/ChoiceZero/QuickeR?style=for-the-badge&labelColor=101418&color=b9c8da)](https://github.com/ChoiceZero/QuickeR/stargazers)
[![License](https://img.shields.io/github/license/ChoiceZero/QuickeR?style=for-the-badge&labelColor=101418&color=d3bfe6)](LICENSE)

**[Download](#download)** · **[Web version](https://choicezero.github.io/QuickeR-Web/)** · **[Website](https://choicezero.github.io/QuickeR-Site/)** · **[How to use](#how-to-use)** · **[Development](#development)**

<a href="docs/screenshots/desktop_create_green_light.png"><img src="docs/screenshots/desktop_create_green_light.png" alt="QuickeR creating a QR code on desktop" width="640"></a>
<a href="docs/screenshots/mobile_library_pink_dark.png"><img src="docs/screenshots/mobile_library_pink_dark.png" alt="QuickeR library on a phone, dark theme" width="166"></a>

</div>

## Why QuickeR?

Most QR websites lock your codes behind an account, expire them after a trial, cover the page in ads or sell your scans as analytics. QuickeR was built out of pure spite towards those practices: it is a free, open-source app that makes QR codes on your own device and never phones home. No personal data, analytics or telemetry is collected. The core code has mostly been written by hand.

<a href="https://buymeacoffee.com/choicezero"><img src="bmac.png" alt="Buy me a coffee" width="180"></a>

## Features

**Create**
- Text and links, Wi-Fi, email, SMS, phone numbers, locations, calendar events and contacts (vCard).
- Live preview that updates on every change.
- Choose the error correction level.
- Custom colors and a logo in the center of the code.

**Organise**
- Every code is saved to a local library, newest first.
- Pin the ones you use most, filter by pinned state and reverse the order.
- Search the library by name or content.
- Import and export the whole library as a `.zip`. QR images made by other apps (PNG, JPG, JPEG, WEBP or SVG) are recognised and added too.

**Export**
- Save as `.png` to your gallery or any folder, or share it straight from the app.
- Export a 3D model (`.stl`) for printing, with the dark modules raised or inset.

**Make it yours**
- Material 3 interface with light and dark themes and several accent colors.
- Separate layouts for desktop and phone screens.
- Available in English, Español, Euskara, Français, Deutsch, Português and Italiano. Switch in **Settings → Customization → Language**; it applies instantly.

<details>
<summary><b>Supported QR types</b></summary>

| Type                     | Supported |
| ------------------------ | :-------: |
| Plain text               | ✅ |
| URL / link               | ✅ |
| Wi-Fi                    | ✅ |
| Email                    | ✅ |
| SMS                      | ✅ |
| Phone number             | ✅ |
| Location                 | ✅ |
| Event                    | ✅ |
| Contact (vCard)          | ✅ |
| Social media & messenger | ❌ |

</details>

## Download

Grab the latest build from the **[Releases page](https://github.com/ChoiceZero/QuickeR/releases/latest)**, or use the **[web version](https://choicezero.github.io/QuickeR-Web/)** with nothing to install.

| Platform | Status | Downloads |
| -------- | :----: | --------- |
| Android  | ✅ | `QuickeR.apk` (or install with [Obtainium](#android-with-obtainium)) |
| Windows  | ✅ | `QuickeR-windows-setup.exe` installer · portable `.zip` |
| Linux    | ✅ | `.AppImage` · `.deb` · `.rpm` · portable `.zip` |
| macOS    | ⚠️ | `.dmg` · portable `.zip` (untested) |
| iOS      | ❌ | Use the [web version](https://choicezero.github.io/QuickeR-Web/) |

> [!WARNING]
> I don't own a Mac, so I can't reliably test the macOS build. It may contain errors.

> [!CAUTION]
> iOS support is dropped for now: Flet's tooling and the platform's restrictions make it too unreliable. The [web version](https://choicezero.github.io/QuickeR-Web/) works perfectly on iPhone and iPad.

### Android with Obtainium

1. In [Obtainium](https://github.com/ImranR98/Obtainium), tap **Add App** and enter `https://github.com/ChoiceZero/QuickeR`.
2. Keep GitHub as the source. Obtainium picks the `.apk` from the latest release (choose your CPU architecture if asked).
3. The app ID is `io.github.choicezero.quicker`.

> [!NOTE]
> Builds up to v1.1.2 were each signed with a different throwaway key, so Android refuses to update over them. If installing fails with a conflict, uninstall the old QuickeR once. Every later build is signed with the same key and updates in place.

### Linux packages

```bash
# Debian / Ubuntu
sudo apt install ./quicker_*_amd64.deb

# Fedora / openSUSE
sudo dnf install ./quicker-*.x86_64.rpm
```

The app is installed to `/opt/quicker`, with a `quicker` command and a menu entry.

<details>
<summary><b>Verifying the package signature</b></summary>

When a release was built with a signing key, the packages are signed and the public key is attached as `QuickeR-signing-key.asc`.

```bash
# .rpm
sudo rpm --import QuickeR-signing-key.asc
rpm -K quicker-*.x86_64.rpm

# .deb (needs the dpkg-sig package)
gpg --import QuickeR-signing-key.asc
dpkg-sig --verify quicker_*_amd64.deb
```

**Maintainers:** to enable signing, set the `LINUX_PACKAGE_GPG_PRIVATE_KEY` repository secret to the output of `gpg --armor --export-secret-keys <KEYID>` and `LINUX_PACKAGE_GPG_PASSPHRASE` to its passphrase. Without them the packages are still built, unsigned. They are built by [`scripts/build-linux-packages.sh`](scripts/build-linux-packages.sh) with [nfpm](https://nfpm.goreleaser.com). Android updates likewise need every release signed with the same key, set by the `ANDROID_KEYSTORE_*` secrets.

</details>

## How to use

<details>
<summary><b>Step-by-step walkthrough</b> (click to expand)</summary>

#### Create a QR

| 1. Tap **+** in the library | 2. Open **Main content** |
| :---: | :---: |
| <img src="docs/screenshots/steps_01_library_plus.png" alt="Library with the + button" width="420"> | <img src="docs/screenshots/steps_02_main_content.png" alt="Main content section" width="420"> |
| **3. Pick the QR type** | **4. Fill in the content** |
| <img src="docs/screenshots/steps_03_qr_type.png" alt="QR type dropdown" width="420"> | <img src="docs/screenshots/steps_04_content.png" alt="Content field" width="420"> |
| **5. Customise colors and logo** | **6. Save it to your library** |
| <img src="docs/screenshots/steps_05_customization.png" alt="Customization section" width="420"> | <img src="docs/screenshots/steps_06_saved_qr.png" alt="Saved QR in the library" width="420"> |

#### Manage and export

| 7. Order and filter the library | 8. Open a QR to see its details |
| :---: | :---: |
| <img src="docs/screenshots/steps_07_order_filter.png" alt="Order and filter controls" width="420"> | <img src="docs/screenshots/steps_08_qr_details.png" alt="QR details" width="420"> |
| **9. Export to gallery, folder or STL** | **10. Choose raised or inset for the 3D model** |
| <img src="docs/screenshots/steps_09_export_options.png" alt="Export options" width="420"> | <img src="docs/screenshots/steps_10_stl_options.png" alt="STL options" width="420"> |
| **11. Import codes from other apps** | |
| <img src="docs/screenshots/steps_11_external_import.png" alt="Importing external QR codes" width="420"> | |

#### Settings

| 12. Language and customisation | 13. Light or dark theme |
| :---: | :---: |
| <img src="docs/screenshots/steps_12_settings_customization.png" alt="Customization settings" width="420"> | <img src="docs/screenshots/steps_13_settings_appearance.png" alt="Appearance settings" width="420"> |
| **14. Accent color** | **15. Library tools: export, import, clear** |
| <img src="docs/screenshots/steps_14_settings_color.png" alt="Color settings" width="420"> | <img src="docs/screenshots/steps_15_settings_tools.png" alt="Library tools" width="420"> |

</details>

<details>
<summary><b>More screenshots</b>: desktop, fullscreen and mobile in every theme</summary>

#### Desktop (1920×1080)

| Library · green / light | QR details · green / light |
| :---: | :---: |
| <a href="docs/screenshots/desktop_library_green_light.png"><img src="docs/screenshots/desktop_library_green_light.png" alt="Desktop library, green light theme" width="420"></a> | <a href="docs/screenshots/desktop_details_green_light.png"><img src="docs/screenshots/desktop_details_green_light.png" alt="Desktop QR details, green light theme" width="420"></a> |
| **Creator · purple / dark** | **QR details · blue / dark** |
| <a href="docs/screenshots/desktop_create_purple_dark.png"><img src="docs/screenshots/desktop_create_purple_dark.png" alt="Desktop QR creator, purple dark theme" width="420"></a> | <a href="docs/screenshots/desktop_details_blue_dark.png"><img src="docs/screenshots/desktop_details_blue_dark.png" alt="Desktop QR details, blue dark theme" width="420"></a> |
| **Settings · orange / light** | **Export dialog · pink / dark** |
| <a href="docs/screenshots/desktop_settings_orange_light.png"><img src="docs/screenshots/desktop_settings_orange_light.png" alt="Desktop settings, orange light theme" width="420"></a> | <a href="docs/screenshots/desktop_export_pink_dark.png"><img src="docs/screenshots/desktop_export_pink_dark.png" alt="Desktop export dialog, pink dark theme" width="420"></a> |

#### Fullscreen (2560×1440)

| QR details · green / light | Creator · blue / dark | Settings · orange / light |
| :---: | :---: | :---: |
| <a href="docs/screenshots/fullscreen_details_green_light.png"><img src="docs/screenshots/fullscreen_details_green_light.png" alt="Fullscreen QR details, green light theme" width="280"></a> | <a href="docs/screenshots/fullscreen_create_blue_dark.png"><img src="docs/screenshots/fullscreen_create_blue_dark.png" alt="Fullscreen QR creator, blue dark theme" width="280"></a> | <a href="docs/screenshots/fullscreen_settings_orange_light.png"><img src="docs/screenshots/fullscreen_settings_orange_light.png" alt="Fullscreen settings, orange light theme" width="280"></a> |

#### Mobile (430×932)

| Library · green / light | Creator · purple / light | QR details · blue / dark | Settings · teal / dark | Settings · indigo / light |
| :---: | :---: | :---: | :---: | :---: |
| <a href="docs/screenshots/mobile_library_green_light.png"><img src="docs/screenshots/mobile_library_green_light.png" alt="Mobile library, green light theme" width="150"></a> | <a href="docs/screenshots/mobile_create_purple_light.png"><img src="docs/screenshots/mobile_create_purple_light.png" alt="Mobile QR creator, purple light theme" width="150"></a> | <a href="docs/screenshots/mobile_details_blue_dark.png"><img src="docs/screenshots/mobile_details_blue_dark.png" alt="Mobile QR details, blue dark theme" width="150"></a> | <a href="docs/screenshots/mobile_settings_teal_dark.png"><img src="docs/screenshots/mobile_settings_teal_dark.png" alt="Mobile settings, teal dark theme" width="150"></a> | <a href="docs/screenshots/mobile_settings_indigo_light.png"><img src="docs/screenshots/mobile_settings_indigo_light.png" alt="Mobile settings, indigo light theme" width="150"></a> |

</details>

## Development

QuickeR is written in Python with [Flet](https://flet.dev) (Flutter under the hood), [qrcode](https://github.com/lincolnloop/python-qrcode), Pillow, OpenCV and NumPy. Python 3.12 or newer is strongly recommended.

### Run

With [uv](https://docs.astral.sh/uv/) (recommended, gives hot reload):

```bash
uv run flet run              # desktop app
uv run flet run --recursive  # desktop app, reload on changes in subfolders
uv run flet run --web        # web app
uv run flet run --android    # on an Android device
```

Without uv, install the dependencies from `pyproject.toml` and drop the `uv run` prefix (no hot reload). See the [Flet getting started guide](https://flet.dev/docs/) for more.

### Test

```bash
uv run pytest
```

The integration tests in [`tests/`](tests) start the real app in-process against a fake Flet client and drive it through UI events: creating, saving, opening and pinning QR codes, plus image, contact and STL export checks. Every pull request also runs them on Linux, Windows and macOS, builds every platform and launches the packaged Linux app with [`scripts/smoke-test-linux.sh`](scripts/smoke-test-linux.sh) (see [`.github/workflows/pr.yml`](.github/workflows/pr.yml)).

### Build

| Target  | Command                   | Guide |
| ------- | ------------------------- | ----- |
| Android | `flet build apk -v`       | [Android packaging](https://flet.dev/docs/publish/android/) |
| Windows | `flet build windows -v`   | [Windows packaging](https://flet.dev/docs/publish/windows/) |
| Linux   | `flet build linux -v`     | [Linux packaging](https://flet.dev/docs/publish/linux/) |
| macOS   | `flet build macos -v`     | [macOS packaging](https://flet.dev/docs/publish/macos/) |
| iOS     | `flet build ipa -v`       | [iOS packaging](https://flet.dev/docs/publish/ios/) |
| Web     | `flet build web -v`       | [Web packaging](https://flet.dev/docs/publish/web/) |

### Translations

All UI texts live in [`src/translations.json`](src/translations.json). The English text is the key, and each entry holds the translation for every other language (a missing translation falls back to English). In the code, texts are written as `tr("Save QR")`, and texts with variables as `tr("Saved to {path}", path=path)`.

- **Fix a translation:** edit its entry in `src/translations.json`.
- **Add a language:** add it to `languages` (code and native name) and add its translation to every entry in `strings`.
- **Add or change a text in the code:** wrap it in `tr(...)` and add it to `src/translations.json`.

Run this before opening a PR. It fails if a text is missing a language or a placeholder doesn't match:

```bash
python scripts/check_translations.py
```

## Related

- [QuickeR-Web](https://github.com/ChoiceZero/QuickeR-Web): the same app in the browser, no install needed ([open it](https://choicezero.github.io/QuickeR-Web/)).
- [QuickeR-Site](https://github.com/ChoiceZero/QuickeR-Site): the project's website ([visit](https://choicezero.github.io/QuickeR-Site/)).

## License

[MIT](LICENSE) © [ChoiceZero](https://github.com/ChoiceZero)
