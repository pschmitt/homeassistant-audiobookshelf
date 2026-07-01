# Audiobookshelf

<img src="logo.png" alt="Audiobookshelf logo" width="300">

Home Assistant custom integration for Audiobookshelf. It polls each book library for newly added items, exposes them as Home Assistant events, and can ask Audiobookshelf to send ebook items to one of its configured e-reader devices.

## Features

- UI config flow, reconfigure flow, reauth flow, options flow, diagnostics, repairs.
- Polls Audiobookshelf on an interval to detect newly added books (Audiobookshelf has no library-item webhook/notification event).
- `event.audiobookshelf_library_item` fires when a new book is detected, with normalized attributes.
- Sensors for server status/version, e-reader devices, default e-reader device, last library item, and send counters.
- Per-library diagnostic sensors for item counts and most recently added books. These are added and removed as Audiobookshelf libraries appear or disappear.
- `select.audiobookshelf_default_e_reader_device` to choose the default Audiobookshelf e-reader device from devices visible to the configured user.
- Buttons to refresh cached server/device data and send the last detected ebook to the selected default e-reader device.
- Duplicate suppression backed by Home Assistant storage.
- Manual `audiobookshelf.send_ebook_to_device` and `audiobookshelf.reset_sent_item` services.
- Uses Audiobookshelf's own e-reader and email settings. Home Assistant does not store SMTP credentials or send mail directly.

## New book detection

Audiobookshelf's notification system has no "library item added" event (only
podcast episode downloads, backups, and RSS failures), so this integration
**polls** each book library's most recently added item on an interval. When a
library's newest item changes, `event.audiobookshelf_library_item` fires and, if
enabled, the book is auto-sent to the default e-reader device. The first poll
after startup only establishes a baseline, so a restart never re-fires or
re-sends existing books.

The event entity emits these event types:

- `library_item_received`
- `library_item_updated`
- `library_item`

Event attributes are normalized for automations. The integration fetches the
full library item from Audiobookshelf so these attributes are populated:

- `item_id`
- `library_id`
- `library_name`
- `title`
- `subtitle`
- `authors`
- `narrators`
- `series`
- `genres`
- `published_year`
- `publisher`
- `description`
- `media_type`
- `has_ebook`
- `ebook_format`
- `duration`
- `added_at`
- `updated_at`
- `cover_url`
- `item_url`
- `source_event`

## Send to e-reader device

Configure SMTP and e-reader devices in Audiobookshelf first. This integration calls the same Audiobookshelf endpoint used by the web UI:

```yaml
action: audiobookshelf.send_ebook_to_device
data:
  item_id: "{{ state_attr('event.audiobookshelf_library_item', 'item_id') }}"
  device_name: "My e-reader"
```

## Branding

This repository bundles Audiobookshelf logo assets (`icon.png`, `logo.png` and
`custom_components/audiobookshelf/brand/`) sourced from the upstream
Audiobookshelf repository. Audiobookshelf and related marks belong to their
respective owners. The integration code is GPL-3.0, but the bundled third-party
logos are not relicensed under GPL. See [`NOTICE.md`](NOTICE.md).

## License

GPL-3.0. Audiobookshelf and related marks belong to their respective owners.
