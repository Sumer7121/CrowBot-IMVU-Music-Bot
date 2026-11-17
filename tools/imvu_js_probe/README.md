# IMVU.js read-only evaluation

This folder is a **non-operational investigation** of the third-party `imvu.js` npm package; it is not an IMVU client or chat integration.

From the CrowBot project directory on Windows:

```powershell
node tools/imvu_js_probe/probe.cjs
```

Requirements: Node.js 18+ and an internet connection. This contacts the public npm registry to retrieve metadata and writes `audit-metadata.json` locally. It **never asks for credentials, installs or executes a package, logs into IMVU, or changes the existing CrowBot listener**.

Review the reported repository link, release version, dependencies, installation scripts, and integrity information before considering a package installation. Source code and packaged tarball still need an independent review before any authenticated test. A marketing feature claim does not verify working IMVU room chat events.

For further investigation consider the independent [@imvu/imq](https://github.com/dhkatz/imvu.js) project, which documents an IMVU messaging WebSocket implementation. It is also unofficial and unverified for current production use.

Never share an IMVU password, session cookie, or token in chat or commit it to GitHub.
