#!/usr/bin/env node
/**
 * Read-only npm package audit. Does not import/install/execute the package,
 * connect to IMVU, or read any account credentials.
 */
const https = require("node:https");
const fs = require("node:fs");
const path = require("node:path");
const {execFileSync} = require("node:child_process");

const pkgName = "imvu.js";
const registry = "https://registry.npmjs.org/imvu.js/latest";
function getJson(url) {
  return new Promise((resolve, reject) => {
    https.get(url, {timeout:12000, headers:{"Accept":"application/json", "User-Agent":"crowbot-package-audit/1"}}, res => {
      if (res.statusCode !== 200) {res.resume(); return reject(new Error("Registry returned HTTP " + res.statusCode));}
      let body = "";
      res.setEncoding("utf8");
      res.on("data", chunk => { body += chunk; if (body.length > 5_000_000) res.destroy(new Error("Metadata too large")); });
      res.on("end", () => {try {resolve(JSON.parse(body));} catch(err) {reject(err);} });
    }).on("error", reject);
  });
}
async function main() {
  console.log("CrowBot third-party dependency audit (NO credentials, NO login)");
  const data = await getJson(registry);
  const result = {
    name:data.name, version:data.version, description:data.description,
    license:data.license, repository:data.repository, homepage:data.homepage,
    engines:data.engines, dependencies:data.dependencies,
    scripts:data.scripts, publishedTarball:data.dist?.tarball,
    integrity:data.dist?.integrity
  };
  console.log(JSON.stringify(result,null,2));
  const output = path.resolve(__dirname, "audit-metadata.json");
  fs.writeFileSync(output, JSON.stringify(result,null,2)+"\n");
  console.log("Saved:",output);
  console.log("Not installed or executed. Review scripts and dependencies before testing in an isolated environment.");
}
main().catch(err => {console.error("Audit unavailable:", err.message);process.exitCode=1;});
