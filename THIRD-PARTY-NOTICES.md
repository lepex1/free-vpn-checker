# Third-party notices

`free-vpn-checker` itself is licensed under the [MIT License](LICENSE).
It downloads, invokes and redistributes nothing on its own, but at runtime it uses the
components below. Their licenses apply to them, not to this project.

## Runtime components

### Xray-core

- Project: <https://github.com/XTLS/Xray-core>
- License: **MPL-2.0**
- How it is used: downloaded automatically (v1.8.24, platform-specific archive from the
  official GitHub releases) into `data/xray/`, launched as a child process for every test.
- Note: the binary is not committed to this repository; it is fetched on first run.

### MaxMind GeoLite2 Country database

- Project mirror used: <https://github.com/P3TERX/GeoLite.mmdb>
- Original data: <https://www.maxmind.com>
- License: **GeoLite2 End User License Agreement** (<https://www.maxmind.com/en/geolite2/eula>)
- How it is used: downloaded to `data/GeoLite2-Country.mmdb`, queried locally to resolve
  the country of each tested server. No data is sent to MaxMind.

## Public configuration sources

The tool only reads these repositories over HTTPS and never redistributes their content
inside this repository. The subscription files it produces are generated on the user's
machine from those public sources.

| Source | License |
|---|---|
| [igareck/vpn-configs-for-russia](https://github.com/igareck/vpn-configs-for-russia) | GPL-3.0 |
| [kort0881/vpn-vless-configs-russia](https://github.com/kort0881/vpn-vless-configs-russia) | GPL-3.0 |

## Python dependencies

See `requirements.txt`. Installed packages keep their own licenses; they are not vendored
into this repository.

## Disclaimer

This project hosts no VPN servers, does not control the servers behind the configs it
tests, and provides no guarantee about their safety, uptime or behaviour. Use at your own
risk and only where it is legal to do so.
