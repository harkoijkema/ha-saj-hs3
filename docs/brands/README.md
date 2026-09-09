# Home Assistant Brands submission bundle

This directory prepares, but does not submit, the exact files for a future
`home-assistant/brands` contribution at:

```text
custom_integrations/saj_hs3/
```

Copy only the two PNG files in `custom_integrations/saj_hs3/` into that external
repository when an upstream contribution is explicitly approved:

- `icon.png` — 256 × 256 pixels;
- `icon@2x.png` — 512 × 512 pixels.

The supplied SAJ HS3 mark is a square icon, so no separate logo assets are
included: the Brands service can use the icon as the logo fallback. The red and
white artwork remains readable on both light and dark surfaces, so a separate
dark variant is not required for the external bundle. The installed integration
does include `dark_icon` variants for Home Assistant's local brand-asset API.

This is a local staging bundle only. It does not create a fork, pull request,
tag or release.
