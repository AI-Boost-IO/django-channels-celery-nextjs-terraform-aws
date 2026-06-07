/**
 * GraphQL Code Generator configuration for Next.js + Apollo Client 4.
 *
 * Generates TypeScript types and typed operation hooks from the Django-exported
 * GraphQL schema. Run after any schema change:
 *
 *   1. python manage.py export_schema graphql.schema --path api/graphql/schema.graphql
 *   2. ./scripts/graphql-sync.sh      (copies schema.graphql to ui/src/)
 *   3. bun run codegen                (runs this config)
 *   4. bun run typecheck              (tsc --noEmit — validates generated types)
 *
 * Output is committed to the repository so CI does not need a running API server.
 *
 * Required packages:
 *   @graphql-codegen/cli
 *   @graphql-codegen/client-preset
 *
 * package.json scripts:
 *   "codegen": "graphql-codegen --config codegen.ts"
 *   "typecheck": "tsc --noEmit"
 */

import type { CodegenConfig } from '@graphql-codegen/cli';

const config: CodegenConfig = {
  // Schema location: synced from the Django export by graphql-sync.sh.
  // Using a local SDL file means codegen never needs a running API server.
  schema: './src/graphql/schema.graphql',

  // Scan all component and page files for gql`` tagged template literals.
  documents: ['src/**/*.tsx', 'src/**/*.ts', '!src/__generated__/**'],

  generates: {
    // All generated types and hooks land in a single __generated__ directory.
    // This directory is committed to the repo and excluded from the documents glob above.
    './src/__generated__/': {
      preset: 'client',
      presetConfig: {
        // gqlTagName: 'gql' — use the `gql` export from the generated index
        // to get typed document nodes with zero runtime overhead.
        gqlTagName: 'gql',
        // fragmentMasking: false — disable fragment masking for simpler prop types.
        // Enable if you adopt the Relay-style fragment colocation pattern.
        fragmentMasking: false,
      },
      config: {
        // Scalar overrides — map Django custom scalars to TypeScript types.
        scalars: {
          UUID: 'string',
          DateTime: 'string',
          Date: 'string',
          Decimal: 'string',
          JSONString: 'string',
          GenericScalar: 'unknown',
        },
        // useTypeImports: true — imports types with `import type` for better
        // tree-shaking and compatibility with `verbatimModuleSyntax`.
        useTypeImports: true,
        // strictScalars: true — raises an error if a scalar is missing from the
        // scalars map above, preventing silent `any` types.
        strictScalars: true,
      },
    },
  },

  // Suppress codegen output noise in CI — set to false for verbose local runs.
  silent: false,

  hooks: {
    afterAllFileWrite: ['prettier --write'],
  },
};

export default config;
