# Firmware Provisioning Investigation

## Objective

Determine the exact provisioning sequence required for Poly UC Software devices to
discover, validate, and download firmware from a local provisioning server.

## Environment

- PolyProv development server
- NGINX reverse proxy
- Firmware Repository implemented
- Rollout Rings implemented
- CCX600 firmware package:
  - Version: `9.4.1.0508`
  - Application image: `3111-49770-001.sip.ld`

## Devices

### Device A

- MAC: `64167fcc45ba`
- Software: `9.4.1.0508`
- Status: Already current

Observed behavior:

- Successfully contacts provisioning server.
- Downloads:
  - `<MAC>.cfg`
  - `<MAC>-phone.cfg`
  - `<MAC>-web.cfg`
  - `<MAC>-license.cfg`
  - `<MAC>-directory.xml`
- Uploads logs.
- Never requests firmware binary.

### Device B

- MAC: `482567b5313f`
- Software: `8.0.2.3267`
- Status: Factory/older firmware
- IP: `10.0.0.142`
- Testing status: Active relative-path firmware experiment

## Experiments

### Experiment 1

`APP_FILE_PATH` emitted under `PHONE_CONFIG/ALL`.

Result:

Phone ignored firmware advertisement.

### Experiment 2

`APP_FILE_PATH` moved into `APPLICATION` element in `<MAC>.cfg`.

Result:

Phone successfully retrieves configuration. NGINX logs later showed the phone did
attempt firmware retrieval, but it constructed malformed URLs from the absolute
`APP_FILE_PATH`:

- `/provisioning//provisioning/firmware/ccx/PVOS_CCX600_9_4_1_0508_release_sig/3111-49770-001.3111-49770-001.sip.ld`
- `/provisioning//provisioning/firmware/ccx/PVOS_CCX600_9_4_1_0508_release_sig/3111-49770-001.sip.ld`

Those requests returned `404` because they did not match the static NGINX
`/provisioning/firmware/` location.

### Experiment 3

`APP_FILE_PATH` changed from an absolute provisioning URL path to a path relative
to the provisioning root.

Previous value:

```xml
APP_FILE_PATH="/provisioning/firmware/ccx/PVOS_CCX600_9_4_1_0508_release_sig/3111-49770-001.sip.ld"
```

New value:

```xml
APP_FILE_PATH="firmware/ccx/PVOS_CCX600_9_4_1_0508_release_sig/3111-49770-001.sip.ld"
```

Result:

Server-side validation passed after cache clear and provisioning API rebuild/restart:
`/provisioning/482567b5313f.cfg` now renders the relative `APP_FILE_PATH`.
A bounded NGINX log watch after deployment saw only validation `curl` requests from
localhost and no fresh Device B-originated request from `10.0.0.142`, so the
device-side firmware download result is still pending the next phone check-in or
reboot.

## Current Hypotheses

1. Poly CCX `8.0.2.3267` appears to treat a leading `/provisioning/...`
   `APP_FILE_PATH` as relative to the already-selected provisioning root, causing
   doubled `/provisioning//provisioning/...` requests.
2. A provisioning-root-relative `APP_FILE_PATH` may resolve to the static firmware
   location correctly.
3. Poly may still require additional `APPLICATION` attributes if relative paths
   resolve but firmware is not accepted.
4. Poly may require a firmware manifest or version comparison before requesting
   firmware.
5. Older firmware may require a staged upgrade before accepting `9.4.x`.
6. Devices already running the target version will never request firmware even
   when correctly advertised.

## Next Experiments

1. Validate the relative `APP_FILE_PATH` experiment on Device B.
2. Confirm whether the phone requests:
   - `/provisioning/firmware/ccx/PVOS_CCX600_9_4_1_0508_release_sig/3111-49770-001.sip.ld`
   - `sip.ver`
   - `*.sha256`
   - another firmware filename
3. If the relative path reaches static firmware but does not upgrade, compare the
   master document more closely against the Poly sample package.
4. Determine whether a staged upgrade path is required only after path handling is
   proven correct.

## Future Design Considerations

Document future support for:

- staged firmware upgrades
- firmware dependency chains
- automatic version graph resolution
- optional Poly Lens metadata import
- offline firmware repository
- firmware integrity verification using SHA256 and signatures
- rollback support
- FIPS/FISMA-friendly operation
- audit logging
- multi-model firmware management
