import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import security from "eslint-plugin-security";
import jsxA11y from "eslint-plugin-jsx-a11y";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  security.configs.recommended,
  // Full jsx-a11y recommended ruleset. Next.js registers the jsx-a11y plugin but only
  // enables a subset of its rules. We extend coverage here by layering in all recommended
  // rules without re-declaring the plugin (which would cause a conflict).
  {
    rules: {
      ...jsxA11y.flatConfigs.recommended.rules,
    },
  },
  {
    rules: {
      // detect-object-injection fires on all bracket-notation access (obj[key]) including
      // typed TypeScript code where keys are constrained — too many false positives to be useful.
      "security/detect-object-injection": "off",

      // autoFocus is used only in interaction-triggered edit fields (inline editing),
      // not on page load — downgrade from error to warn so the intent is visible but
      // doesn't block the build.
      "jsx-a11y/no-autofocus": "warn",

      // Respect the _name convention for intentionally unused destructured values.
      "@typescript-eslint/no-unused-vars": ["error", { "varsIgnorePattern": "^_", "argsIgnorePattern": "^_" }],
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
