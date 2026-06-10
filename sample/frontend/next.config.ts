import type { NextConfig } from 'next';

/**
 * Next.js 16 configuration.
 *
 * Turbopack is the default bundler for both `next dev` and `next build` in
 * Next.js 16 — no flags or experimental keys required. The `turbopack` block
 * below is only needed when you require custom loader rules or resolve aliases.
 * Remove it entirely if you have no customisation needs.
 *
 * To opt out of Turbopack (not recommended — webpack support is dropped in
 * Next.js 16), stay on Next.js 15 which receives security patches.
 */
const nextConfig: NextConfig = {
  /**
   * Turbopack configuration (top-level in Next.js 16, was
   * `experimental.turbopack` in Next.js 15).
   *
   * Common customisations are shown below — delete what you don't need.
   */
  turbopack: {
    /**
     * Resolve aliases — equivalent to webpack's `resolve.alias`.
     * Map short import paths to source directories in your monorepo.
     *
     * Example:
     *   import { Button } from '@ui/Button'
     *   resolves to   ./packages/ui/src/Button
     */
    resolveAlias: {
      // '@ui': './packages/ui/src',
    },

    /**
     * Custom loader rules — equivalent to webpack's `module.rules`.
     * Only add entries here for file types that need a non-default transform.
     *
     * Example: import SVGs as React components via @svgr/webpack
     *   '*.svg': { loaders: ['@svgr/webpack'], as: '*.js' }
     */
    rules: {
      // '*.svg': { loaders: ['@svgr/webpack'], as: '*.js' },
    },
  },
};

export default nextConfig;
