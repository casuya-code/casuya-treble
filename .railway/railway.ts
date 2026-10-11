import { defineRailway, github, postgres, preserve, project, service, volume } from "railway/iac";

export default defineRailway(() => {
  const Postgres = postgres("Postgres", { region: "sfo" });
  Postgres.networking = { privateNetworkEndpoint: "postgres" };
  const postgresVolume = volume("postgres-volume", { alerts: { usage: { "100": {}, "80": {}, "95": {} } }, allowOnlineResize: true, region: "sfo", sizeMB: 5000 });
  const web = service("web", {
    source: github("casuya-code/casuya-treble", { rootDirectory: "apps/dashboard" }),
    build: { builder: "DOCKERFILE", dockerfilePath: "Dockerfile" },
    healthcheck: "/",
    healthcheckTimeout: 120,
    replicas: { "sfo": 1 },
    env: { NEXT_PUBLIC_API_URL: preserve() },
  });
  const api = service("api", {
    source: github("casuya-code/casuya-treble", { rootDirectory: "core-prediction-engine" }),
    build: { builder: "DOCKERFILE", dockerfilePath: "Dockerfile" },
    healthcheck: "/health",
    healthcheckTimeout: 120,
    replicas: { "sfo": 1 },
    env: { ADMIN_EMAIL: preserve(), ADMIN_PASSWORD: preserve(), APP_PUBLIC_URL: preserve(), CORS_ORIGINS: preserve(), DATABASE_URL: preserve(), EXPOSE_PASSWORD_RESET_LINK: preserve(), JWT_SECRET: preserve() },
  });

  return project("casuya-treble", {
    resources: [web, Postgres, api, postgresVolume],
  });
});
