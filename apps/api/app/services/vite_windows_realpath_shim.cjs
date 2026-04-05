const fs = require("node:fs");
const path = require("node:path");

const originalNativeRealpath = fs.realpathSync.native;
const cwdRealpathProbe = path.resolve("./");
let handledFirstProbe = false;

fs.realpathSync.native = function patchedNativeRealpath(targetPath, ...args) {
  if (!handledFirstProbe && targetPath === cwdRealpathProbe) {
    handledFirstProbe = true;
    const error = new Error("EISDIR: illegal operation on a directory");
    error.code = "EISDIR";
    throw error;
  }
  return originalNativeRealpath.call(this, targetPath, ...args);
};
