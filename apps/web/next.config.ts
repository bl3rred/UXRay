import fs from "node:fs";
import path from "node:path";
import type { NextConfig } from "next";

const repoRootEnvPath = path.resolve(__dirname, "../../.env.local");

function normalizeEnvValue(rawValue: string) {
  const trimmedValue = rawValue.trim();

  if (
    (trimmedValue.startsWith('"') && trimmedValue.endsWith('"')) ||
    (trimmedValue.startsWith("'") && trimmedValue.endsWith("'"))
  ) {
    return trimmedValue.slice(1, -1);
  }

  return trimmedValue;
}

function loadRootPublicEnv(filePath: string) {
  if (!fs.existsSync(filePath)) {
    return {} as Record<string, string>;
  }

  const fileContents = fs.readFileSync(filePath, "utf8");
  const env: Record<string, string> = {};

  for (const line of fileContents.split(/\r?\n/)) {
    const trimmedLine = line.trim();

    if (!trimmedLine || trimmedLine.startsWith("#")) {
      continue;
    }

    const exportlessLine = trimmedLine.startsWith("export ")
      ? trimmedLine.slice("export ".length)
      : trimmedLine;
    const separatorIndex = exportlessLine.indexOf("=");

    if (separatorIndex <= 0) {
      continue;
    }

    const key = exportlessLine.slice(0, separatorIndex).trim();
    if (!key.startsWith("NEXT_PUBLIC_")) {
      continue;
    }

    const parsedValue = normalizeEnvValue(exportlessLine.slice(separatorIndex + 1));
    const effectiveValue = process.env[key] ?? parsedValue;

    process.env[key] = effectiveValue;
    env[key] = effectiveValue;
  }

  return env;
}

const rootPublicEnv = loadRootPublicEnv(repoRootEnvPath);

const nextConfig: NextConfig = {
  env: rootPublicEnv,
  reactStrictMode: true,
};

export default nextConfig;
