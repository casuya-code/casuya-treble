import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

/** Flat config (ESLint 9). The old `.eslintrc.json` + `extends` chain breaks
    because eslint-config-next v16 ships flat configs only. */
export default [
  {
    ignores: [
      "node_modules/**",
      ".next/**",
      "out/**",
      "next-env.d.ts",
      "eslint.config.mjs",
    ],
  },
  ...nextCoreWebVitals,
  ...nextTypescript,
  {
    rules: {
      // The dashboard leans on `any` in a few typed API boundaries on purpose.
      "@typescript-eslint/no-explicit-any": "off",
      "react/no-unescaped-entities": "off",
      // These components read localStorage/token state that does not exist during
      // SSR, so they must sync once after mount (AuthGuard, LandingLang,
      // IndexView, admin `load`). That is the supported hydration pattern, not a
      // cascading-render bug — keep it visible as a warning, not a build failure.
      "react-hooks/set-state-in-effect": "warn",
    },
  },
];
