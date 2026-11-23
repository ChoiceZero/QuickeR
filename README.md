<img width="1345" height="247" alt="Diseño sin título" src="https://github.com/user-attachments/assets/f661f708-ef80-4ae7-8e3b-78a397f6af3c" />

![GitHub last commit](https://img.shields.io/github/last-commit/ChoiceZero/QuickeR?style=for-the-badge&labelColor=101418&color=9ccbfb)
![GitHub Repo stars](https://img.shields.io/github/stars/ChoiceZero/QuickeR?style=for-the-badge&labelColor=101418&color=b9c8da)
![GitHub repo size](https://img.shields.io/github/repo-size/ChoiceZero/QuickeR?style=for-the-badge&labelColor=101418&color=d3bfe6)

# QuickeR - Create QRs quicker!

QuickeR is a platform that lets you create QR codes but without accounts, limits, ads or purchases. It also doesn't collect any personal data, analytics, telemetry or other kind of info. It was primarily created out of pure spite, as most other websites have shitty practices to get the most revenue out of users. Besides, the core code has mostly been written by hand.

<a href="https://buymeacoffee.com/choicezero">
  <img src="bmac.png" alt="Descriptive text" width="200">
</a>

## Features

- Cross platform.
- Creates QRs from these types:

| Type                          | Support   |
| ----------------------------- | --------- |
| Plain text                    | ✅        |
| URL/Link                      | ✅        |
| Social Media & Messenger      | ❌        |
| Wifi                          | ✅        |
| Email                         | ✅        |
| SMS                           | ✅        |
| Phone number                  | ✅        |
| Email                         | ✅        |
| Location                      | ✅        |
| Event                         | ✅        |
| Contact (vCard)               | ✅        |

- Allows to place logos in the center of the QR.
- Allows to change the colors of the QRs.
- Has a preview that updates on every change.
- Downloads the codes.
- Has a summary view before downloading the QR code.
- Uses a Material3-like user interface.
- Available in English, Español, Euskara, Français, Deutsch, Português and Italiano. Change it in Settings → Customization → Language; the app updates instantly and remembers your choice.

## Supported devices and current release types

| Device                        | Support   | Installer/Packaged | Standalone |
| ----------------------------- | --------- | ------------------ | ---------  |
| Linux                         | ✅        | ✅                 | ✅         |
| Android                       | ✅        | ✅                 | *          |
| Windows                       | ✅        | ✅                 | ✅         |
| IOs                           | ❌        | ❌                 | ❌         |
| MacOs                         | ~         | ✅                 | ✅         |

>[!CAUTION]
>Due to IOs working unreliably with Flet's tools and limitations at operating system level, support has to be dropped for the time being. However, the web version (QuickeR-Web) can be used perfectly.

>[!WARNING]
>I cannot reliably test the MacOs build, as I don't own a Mac. Build may contain errors.

>[!TIP]
>*There is no Android standalone because android works with just .APK.

## Installing on Android with Obtainium

1. In [Obtainium](https://github.com/ImranR98/Obtainium), choose **Add App** and enter `https://github.com/ChoiceZero/QuickeR`.
2. Source: GitHub. Obtainium picks the `.apk` from the latest release (choose your CPU architecture if asked).
3. The Android app ID is `io.github.choicezero.quicker`.

Updates require every release to be signed with the same key (set by the `ANDROID_KEYSTORE_*` repository secrets).

>[!NOTE]
>Builds up to v1.1.2 were each signed with a different throwaway key, so Android refuses to update over them. If the install fails with a conflict, uninstall the old QuickeR once; every build after that is signed with the same key and updates in place.

## Translations

All UI texts live in [`src/translations.json`](src/translations.json). The English text is the key, and each entry holds the translation for every other language (a missing translation falls back to English). In the code, texts are written as `tr("Save QR")`, and texts with variables as `tr("Saved to {path}", path=path)`.

- **Fix a translation:** edit its entry in `src/translations.json`.
- **Add a language:** add it to `languages` (code and native name) and add its translation to every entry in `strings`.
- **Add or change a text in the code:** wrap it in `tr(...)` and add it to `src/translations.json`.

Run this before opening a PR. It fails if a text is missing a language or a placeholder doesn't match:

```bash
python scripts/check_translations.py
```

## Tech Stack

**Python moules:** Flet, Qrcode, Pillow and other libraries that base Python includes.

**Actually running the code:** Flutter, Dart.


## License

[MIT](https://choosealicense.com/licenses/mit/)

## Run the app
>[!WARNING]
>It is heavily recommended to use Python 3.12 or above to run the app.

### flet

Run as a desktop app:

```bash
flet run
```

Run recursively as a desktop app:

```bash
flet run --recursive
```

Run as a web app:

```bash
flet run --web
```

Run as an android app:

```bash
flet run --android
```

### uv

Run as a desktop app:

```bash
uv run flet run
```

Run recursively as a desktop app:
```bash
uv run flet run --recursive
```

Run as a web app:

```bash
uv run flet run --web
```

Run as an android app:

```bash
uv run flet run --android
```

For more details on running the app, refer to the [Getting Started Guide](https://flet.dev/docs/).

## Build the app
>[!WARNING]
>It is heavily recommended to use Python 3.12 or above to compile the app.

### Android

```bash
flet build apk -v
```

For more details on building and signing `.apk` or `.aab`, refer to the [Android Packaging Guide](https://flet.dev/docs/publish/android/).

### iOS

```bash
flet build ipa -v
```

For more details on building and signing `.ipa`, refer to the [iOS Packaging Guide](https://flet.dev/docs/publish/ios/).

### macOS

```bash
flet build macos -v
```

For more details on building macOS package, refer to the [macOS Packaging Guide](https://flet.dev/docs/publish/macos/).

### Linux

```bash
flet build linux -v
```

For more details on building Linux package, refer to the [Linux Packaging Guide](https://flet.dev/docs/publish/linux/).

### Windows

```bash
flet build windows -v
```

For more details on building Windows package, refer to the [Windows Packaging Guide](https://flet.dev/docs/publish/windows/).

### Web

```bash
flet build web -v
```

For more details on building Web app, refer to the [Web Packaging Guide](https://flet.dev/docs/publish/web/).


## Authors

- [@ChoiceZero](https://www.github.com/ChoiceZero)


## Related

A desktop app is also available for Linux, Windows and Android.

[Desktop app repository (QuickeR)](https://github.com/ChoiceZero/QuickeR)

