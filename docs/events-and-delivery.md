# Events and delivery

Audiobookshelf has no notification for newly added library items, so the
integration polls each book library's newest item. The first poll after startup
establishes a baseline without firing an event or sending an existing book.
Subsequent changes fire `event.audiobookshelf_library_item`. Duplicate
suppression persists in Home Assistant storage.

The event entity emits `library_item_received`, `library_item_updated`, and
`library_item` events. It fetches the full library item and exposes these
normalized attributes for automations:

- `item_id`, `library_id`, `library_name`
- `title`, `subtitle`, `authors`, `narrators`, `series`, `genres`
- `published_year`, `publisher`, `description`, `media_type`
- `has_ebook`, `ebook_format`, `duration`
- `added_at`, `updated_at`, `cover_url`, `item_url`, `source_event`

## Sending an ebook

Set up SMTP and e-reader devices in Audiobookshelf first. The integration calls
the same Audiobookshelf endpoint as the web UI; Home Assistant does not store
SMTP credentials or send mail directly. Choose a default device with
`select.audiobookshelf_default_e_reader_device`, or call the service with a
specific device:

```yaml
action: audiobookshelf.send_ebook_to_device
data:
  item_id: "{{ state_attr('event.audiobookshelf_library_item', 'item_id') }}"
  device_name: "My e-reader"
```

Use `audiobookshelf.reset_sent_item` to clear a sent-item record if you need to
send it again.
