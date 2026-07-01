# Audiobookshelf

<img src="logo.png" alt="Audiobookshelf logo" width="300">

Home Assistant custom integration for Audiobookshelf. The first implemented feature sends new ebook items to a Kindle personal document address.

## Features

- UI config flow, reconfigure flow, reauth flow, options flow, diagnostics, repairs.
- Secure webhook endpoint for Audiobookshelf notifications.
- Duplicate suppression backed by Home Assistant storage.
- Manual `audiobookshelf.send_item` and `audiobookshelf.reset_sent_item` services.
- Optional local path mapping when Home Assistant can see the same library files as Audiobookshelf.

## Audiobookshelf notification URL

After setup, use the configured webhook path sensor:

```text
https://<home-assistant>/api/webhook/<webhook_id>
```

The integration accepts common ABS notification payload shapes containing `libraryItemId`, `itemId`, `id`, or a nested `item.id` / `libraryItem.id`.

## Branding

This repository bundles Audiobookshelf logo assets (`icon.png`, `logo.png` and
`custom_components/audiobookshelf/brand/`) sourced from the upstream
Audiobookshelf repository. Audiobookshelf and related marks belong to their
respective owners. The integration code is GPL-3.0, but the bundled third-party
logos are not relicensed under GPL. See [`NOTICE.md`](NOTICE.md).

## License

GPL-3.0. Audiobookshelf and related marks belong to their respective owners.
