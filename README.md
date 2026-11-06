# SAM INCUS CLOUD — Pterodactyl Egg

This egg is a lifecycle wrapper, not an Incus installation. It runs in a Pterodactyl Docker container and calls a remote Incus HTTPS API to create/start one Incus **container**. Pterodactyl Stop stops that Incus instance.

## Requirements
- Incus API reachable from the Wings Docker network over HTTPS.
- Dedicated restricted Incus TLS client certificate trusted by the Incus server.
- Dedicated Incus project, storage pool, and bridge (defaults: `default`, `incusbr0`).
- Image alias available on the Incus server, e.g. `images:debian/13`.
- Never expose the client private key or make it customer-editable.

## Install
1. Pterodactyl Admin → Nests → Import Egg → import `egg-sam-incus-vps.json`.
2. Create a server using this egg and Docker image `python:3.12-slim`.
3. Upload `incus_egg.py` to the server root using File Manager/SFTP.
4. Set `INCUS_API_URL` to the private HTTPS API address reachable from Wings.
5. Set `INCUS_PROJECT`, certificate/key paths, optional CA path, image, RAM, CPU, disk, pool and bridge.
6. Place the matching client certificate and private key at those paths. Restrict access to the files.
7. Run Install, then Start.

## Important limitations
- This initial egg creates Incus containers, not full virtual machines.
- Pterodactyl Start creates/starts the Incus instance; Stop stops it.
- Deleting a Pterodactyl server does NOT delete the Incus instance. Add a separately authenticated admin cleanup workflow before production.
- Reinstall does not delete/recreate an existing Incus instance.
- The Pterodactyl container's own resource limits are separate from the Incus VPS limits.
- NAT, port allocation, public SSH access, firewall rules, and IP delivery are not configured by this egg.
- Do not expose Incus port 8443 publicly. Use private networking, trusted TLS, and a restricted project-scoped certificate/authorization policy.
- Keep TLS verification enabled. Configure a trusted server CA rather than setting `INCUS_TLS_VERIFY=false`.
- Incus API credentials are powerful; never share an unrestricted host certificate with customers.

## Troubleshooting
- Connection refused/timeout: check Incus listener, firewall and Wings-to-Incus routing.
- 401/403: client certificate trust or project permissions are incorrect.
- Image not found: verify the image alias on the Incus host.
- Pool/bridge errors: configure names of existing Incus resources.
