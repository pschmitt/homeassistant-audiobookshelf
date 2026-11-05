<p align="center">
  <img src="logo.png" width="128" alt="Audiobookshelf logo">
</p>

<p align="center">
  <a href="https://my.home-assistant.io/redirect/marketplace_repository/?owner=pschmitt&amp;repository=homeassistant-audiobookshelf&amp;category=integration"><img src="https://my.home-assistant.io/badges/marketplace_repository.svg" alt="Open this integration in Home Assistant Marketplace"></a>
</p>

<h1 align="center">Audiobookshelf for Home Assistant</h1>

<p align="center">Detect new books in Audiobookshelf libraries and send ebooks to a configured e-reader.</p>

## Features

- **Library events:** Poll for newly added books and emit `event.audiobookshelf_library_item` with normalized metadata; the first poll establishes a baseline.
- **E-reader delivery:** Automatically send new ebooks to a default device, or call a service to send a specific item. See [Events and delivery](docs/events-and-delivery.md).
- **Sensors and controls:** Show server status, e-reader devices, recent items, send counts, and per-library diagnostics; select a default device or refresh cached data.
- **Configuration:** Set up and reconfigure in the UI, with options, reauthentication, diagnostics and repairs.

## Install

Use the Marketplace badge above on Home Assistant 2026.11 or later to add this
repository as a custom integration. On older versions, add it as a HACS
custom repository of type **Integration**. Install and restart Home Assistant.
The badge does not imply a public catalog listing.

## Quick start

1. Add **Audiobookshelf** under **Settings → Devices & services → Add integration** and configure your server.
2. Configure SMTP and an e-reader device in Audiobookshelf if you want ebook delivery.
3. Select a default e-reader in Home Assistant, then watch for new-library-item events.

## Documentation

| Topic | Description |
|-------|-------------|
| [Events and delivery](docs/events-and-delivery.md) | Event attributes, duplicate suppression, and ebook sending |

## License

[GPL-3.0](LICENSE). Audiobookshelf logos belong to their respective owners and
are not relicensed under GPL; see [NOTICE.md](NOTICE.md).
