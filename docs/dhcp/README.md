# DHCP Discovery for Poly Provisioning

Poly phones locate the provisioning server through DHCP options. PolyProv
recommends **Option 160** (and **161** for cross-firmware compatibility), with
**Option 66** as a legacy fallback.

| Option | Meaning | PolyProv use |
|--------|---------|--------------|
| 160 | Poly provisioning server URL (string) | **Primary.** Full URL incl. scheme. |
| 161 | Provisioning server address (string) | Set equal to 160 for older firmware. |
| 66  | TFTP server name (legacy) | Fallback. Hostname or URL. |

Set the value to your provisioning base URL, e.g.
`https://prov.example.com/provisioning/`. HTTPS works directly via option 160.

> **Most common field failure:** Option 160 sent as a *binary* option instead of
> a *string/text* option. Always declare it as text.

---

## ISC dhcpd (Linux)

```
option poly-160 code 160 = text;
option poly-161 code 161 = text;

subnet 10.20.0.0 netmask 255.255.0.0 {
  range 10.20.10.10 10.20.10.250;
  option routers 10.20.0.1;
  option domain-name-servers 10.20.0.2;

  option poly-160 "https://prov.example.com/provisioning/";
  option poly-161 "https://prov.example.com/provisioning/";

  # legacy fallback (older Poly/Polycom firmware)
  option tftp-server-name "prov.example.com";
}
```

## Windows Server DHCP

1. Open DHCP console → IPv4 → Scope/Server Options → Configure Options →
   Advanced.
2. Define custom option **160** as **String**. Set value to
   `https://prov.example.com/provisioning/`.
3. Repeat for option **161** with the same value.
4. (Legacy) Set predefined option **066 Boot Server Host Name** to
   `prov.example.com`.

Define the custom option once (Server → Set Predefined Options → Add):
- Name: `Poly-Prov-160`, Data type: `String`, Code: `160`.

## Cisco IOS DHCP

```
ip dhcp pool VOICE
 network 10.20.0.0 255.255.0.0
 default-router 10.20.0.1
 dns-server 10.20.0.2
 option 160 ascii "https://prov.example.com/provisioning/"
 option 161 ascii "https://prov.example.com/provisioning/"
 option 66  ascii "prov.example.com"
```

## MikroTik RouterOS

```
/ip dhcp-server option
add code=160 name=poly-160 value="'https://prov.example.com/provisioning/'"
add code=161 name=poly-161 value="'https://prov.example.com/provisioning/'"
/ip dhcp-server network
set [find] dhcp-option=poly-160,poly-161
```

---

## Verifying discovery

1. Boot a phone on the VoIP VLAN.
2. Confirm it requested `000000000000.cfg` then `<MAC>.cfg` from the URL:
   `tail -f` the prov NGINX access log or watch
   `polyprov_provisioning_requests_total` in Prometheus.
3. A 404 for an unknown MAC means the device isn't enrolled — import it first.

## Notes on HTTP vs HTTPS

- HTTPS via option 160 requires the phone to trust your CA. Poly devices ship
  with common public roots; for a private CA you must push the cert (via a
  config parameter `sec.TLS.customCaCert.x`) or use a publicly-trusted cert.
- HTTP provisioning is supported for legacy fleets but logged and flagged.
  Never serve registration credentials over plain HTTP in production.
