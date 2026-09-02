# Third-party notices

## Redistributed browser dependencies

The static site ships these locked, self-hosted third-party files (see
`site/assets/vendor/README.md` for versions, checksums, and upgrade policy):

- Cytoscape.js (`cytoscape.min.js`) — MIT license, full text in
  `site/assets/vendor/cytoscape.LICENSE`.

## Optional upstream projects

This repository can install, but does not redistribute, the following optional upstream projects:

- op7418/guizang-social-card-skill — currently AGPL-3.0 according to its upstream repository.
- op7418/guizang-material-illustration — inspect and record its upstream license during installation.

`python briefing.py setup --vendor` records installed commits in `vendor-installed.json`.
