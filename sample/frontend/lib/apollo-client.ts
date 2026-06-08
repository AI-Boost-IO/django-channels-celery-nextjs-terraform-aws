/**
 * Apollo Client 4 setup for Next.js 16 App Router — client-side module.
 *
 * Uses @apollo/client-integration-nextjs (replaces @apollo/experimental-nextjs-app-support).
 *
 * This file is a 'use client' module. It exports:
 *   - makeClient()    → factory used by ApolloWrapper and rsc-client.ts
 *   - ApolloWrapper   → root Client Component provider for the App Router
 *
 * For React Server Component (RSC) queries, import from lib/rsc-client.ts instead:
 *   import { getClient } from '@/lib/rsc-client';
 *
 * The link chain splits traffic by operation type:
 *   - subscription → GraphQLWsLink (WebSocket via graphql-ws)
 *   - query/mutation → HttpLink (standard fetch)
 *
 * Required peer dependencies (install explicitly — not bundled by Apollo):
 *   bun add graphql-ws rxjs
 *
 * Environment variables (set in Vercel dashboard, not vercel.json):
 *   NEXT_PUBLIC_API_URL  — browser-facing HTTP API base URL
 *   NEXT_PUBLIC_WS_URL   — browser-facing WebSocket URL
 *   SSR_API_URL          — server-side HTTP URL (internal in dev, same as API URL in prod)
 *
 * See docs/05-frontend.md for the full Apollo + Next.js pattern.
 */

'use client';

import {
  ApolloClient,
  ApolloLink,
  HttpLink,
  InMemoryCache,
  split,
} from '@apollo/client';
import { ApolloNextAppProvider } from '@apollo/client-integration-nextjs';
import { GraphQLWsLink } from '@apollo/client/link/subscriptions';
import { getMainDefinition } from '@apollo/client/utilities';
import { createClient } from 'graphql-ws';
import React from 'react';

// ---------------------------------------------------------------------------
// Cookie helper — reads the JWT from an HttpOnly cookie set by Django
// ---------------------------------------------------------------------------

/**
 * Read the access token from a cookie.
 * Replace with your own auth token retrieval (localStorage, cookie, etc.).
 */
function getAccessToken(): string {
  if (typeof document === 'undefined') {
    return '';
  }
  const match = document.cookie.match(/(?:^|;\s*)access_token=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : '';
}

// ---------------------------------------------------------------------------
// Links
// ---------------------------------------------------------------------------

/**
 * HTTP link for queries and mutations.
 *
 * SSR_API_URL is used server-side so Next.js can reach the Django container
 * directly (e.g. http://api:8000 in Docker) without going through the public
 * domain. In production both URLs are the same (https://api.example.com).
 */
function makeHttpLink(): HttpLink {
  const uri =
    typeof window === 'undefined'
      ? (process.env.SSR_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? '')
      : (process.env.NEXT_PUBLIC_API_URL ?? '');

  return new HttpLink({
    uri: `${uri}/api/v1`,
    // credentials: 'include' sends session cookies for Django session auth.
    // Remove if you use token-based auth exclusively.
    credentials: 'include',
  });
}

/**
 * WebSocket link for GraphQL subscriptions.
 *
 * The JWT is passed in connectionParams so Django's JwtAuthMiddleware can
 * authenticate the WebSocket connection before the subscription begins.
 *
 * rxjs is a required peer dependency for graphql-ws + Apollo — install it explicitly.
 */
function makeWsLink(): GraphQLWsLink {
  return new GraphQLWsLink(
    createClient({
      url: `${process.env.NEXT_PUBLIC_WS_URL ?? ''}/api/v1`,
      connectionParams: () => {
        const token = getAccessToken();
        return token ? { authorization: `Bearer ${token}` } : {};
      },
      // Reconnect automatically on connection loss
      retryAttempts: Infinity,
      shouldRetry: () => true,
    }),
  );
}

/**
 * Split link: route subscription operations to WebSocket, everything else to HTTP.
 *
 * This split is browser-only — WebSocket connections are never created server-side
 * (the `typeof window` guard in makeClient prevents that).
 */
function makeSplitLink(httpLink: HttpLink): ApolloLink {
  const wsLink = makeWsLink();

  return split(
    ({ query }) => {
      const definition = getMainDefinition(query);
      return (
        definition.kind === 'OperationDefinition' &&
        definition.operation === 'subscription'
      );
    },
    wsLink,   // subscriptions → WebSocket
    httpLink, // queries + mutations → HTTP
  );
}

// ---------------------------------------------------------------------------
// Client factory
// ---------------------------------------------------------------------------

/**
 * Create a new Apollo Client instance.
 *
 * Called once per:
 *   - Browser session (makeClient is called in ApolloWrapper on mount)
 *   - RSC request (registerApolloClient in rsc-client.ts calls this per request)
 *
 * InMemoryCache is configured with type policies to normalise UUID-keyed
 * objects correctly across paginated and subscription results.
 */
export function makeClient(): ApolloClient<unknown> {
  const httpLink = makeHttpLink();
  const link = typeof window === 'undefined' ? httpLink : makeSplitLink(httpLink);

  return new ApolloClient({
    cache: new InMemoryCache({
      typePolicies: {
        // Normalise ExampleItemType by its `id` field (UUID string).
        // Replace with your own types.
        ExampleItemType: {
          keyFields: ['id'],
        },
      },
    }),
    link,
    // Apollo v4 devtools API — automatically inactive in production builds.
    devtools: { enabled: process.env.NODE_ENV === 'development' },
  });
}

// ---------------------------------------------------------------------------
// ApolloWrapper — root Client Component provider
// ---------------------------------------------------------------------------

/**
 * ApolloWrapper provides the Apollo client to all Client Components via context.
 *
 * Place this at the root layout so every Client Component can call
 * useQuery / useSuspenseQuery / useSubscription.
 *
 * Usage in app/layout.tsx:
 *   import { ApolloWrapper } from '@/lib/apollo-client';
 *   <ApolloWrapper>{children}</ApolloWrapper>
 */
export function ApolloWrapper({ children }: { children: React.ReactNode }) {
  return (
    <ApolloNextAppProvider makeClient={makeClient}>
      {children}
    </ApolloNextAppProvider>
  );
}
