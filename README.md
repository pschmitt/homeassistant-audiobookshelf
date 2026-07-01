# Audiobookshelf

<img src="logo.png" alt="Audiobookshelf logo" width="300">

Home Assistant custom integration for Audiobookshelf. The first implemented feature exposes Audiobookshelf webhooks as Home Assistant events and can ask Audiobookshelf to send ebook items to one of its configured e-reader devices.

## Features

- UI config flow, reconfigure flow, reauth flow, options flow, diagnostics, repairs.
- Secure webhook endpoint for Audiobookshelf notifications.
- `event.audiobookshelf_library_item` for normalized library item webhook events.
- Sensors for server status/version, e-reader devices, default e-reader device, last library item, send counters, and webhook URL.
- `select.audiobookshelf_default_e_reader_device` to choose the default Audiobookshelf e-reader device from devices visible to the configured user.
- Buttons to refresh cached server/device data and send the last received ebook to the selected default e-reader device.
- Duplicate suppression backed by Home Assistant storage.
- Manual `audiobookshelf.send_ebook_to_device` and `audiobookshelf.reset_sent_item` services.
- Uses Audiobookshelf's own e-reader and email settings. Home Assistant does not store SMTP credentials or send mail directly.

## Audiobookshelf notification URL

After setup, use the configured webhook path sensor:

```text
https://<home-assistant>/api/webhook/<webhook_id>
```

The integration accepts common ABS notification payload shapes containing `libraryItemId`, `itemId`, `id`, or a nested `item.id` / `libraryItem.id`.

The event entity emits these event types:

- `library_item_received`
- `library_item_updated`
- `library_item`

Event attributes are normalized for automations:

- `item_id`
- `library_id`
- `title`
- `authors`
- `media_type`
- `has_ebook`
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
