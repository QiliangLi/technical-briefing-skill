# Self-hosted third-party browser assets

The workbench loads no CDN scripts and makes no runtime third-party requests.
Every browser dependency in this directory is a committed, version-locked
distribution file with its upstream license beside it.

| File | Package | Version | Upstream | License |
| --- | --- | --- | --- | --- |
| `cytoscape.min.js` | Cytoscape.js | 3.34.2 | https://github.com/cytoscape/cytoscape.js (npm `cytoscape`) | MIT (`cytoscape.LICENSE`) |

`cytoscape.min.js` is the upstream UMD minified distribution, byte-for-byte as
published on npm (`cytoscape@3.34.2`, `dist/cytoscape.min.js`).

- SHA-256: `b85c213252b880cbb2d86c10dc537f673560e82494da4330f1ccc18fbcb5f145`
- Upgrade policy: replace the file, update this table (version, checksum), and
  re-run the graph-surface tests. Never patch the file in place.
