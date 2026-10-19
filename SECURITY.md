# Security

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting:

https://github.com/roboalchemist/kicad-agent/security/advisories/new

Do not open a public issue for a security problem. Include the affected component
(agent, engine, server, web UI), a reproduction, and the impact you expect.

## Scope notes

- The harness executes real KiCad tooling and can spawn an autorouter JVM. It is
  designed to run on your own machine against your own design files.
- `kicad-harness serve` has no authentication. It binds to localhost by default and
  is not intended to be exposed to a network.
- Model providers receive the prompts and board context the agent sends. Review your
  provider's data policy before pointing it at proprietary designs.
