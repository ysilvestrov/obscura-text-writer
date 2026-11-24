
## Fix round 1
Markdown paragraph whose visible text contains a newline is an opaque block (list/quote): emitted verbatim, offsets 1:1. Added test_opaque_blocks_roundtrip (list with emphasis chars, blockquote). Probe (scenes exact roundtrip_ok idempotent): `154 139 154 154`. tests/authoring tests/publication: 334 passed.
