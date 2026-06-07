/**
 * Apollo Client 4 setup for Next.js 16 App Router.
 *
 * Uses @apollo/client-integration-nextjs (replaces @apollo/experimental-nextjs-app-support).
 *
 * Two client factories are exported:
 *   - makeClient()         → used by ApolloWrapper (Client Components, browser)
 *   - registerApolloClient → used by getClient() for RSC / Server Component queries
 *
 * The link chain splits traffic by operation type:
 *   - subscription → GraphQLWsLink (WebSocket via graphql-ws)
 *   - query/mutation → HttpLink (standard fetch)
 *
 * Required peer dependencies (install explicitly — not bundled by Apollo):
 *   npm install graphql-ws rxjs
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
import { registerApolloClient } from '@apollo/client-integration-nextjs';
import { GraphQLWsLink } from '@apollo/client/link/subscriptions';
import { getMainDefinition } from '@apollo/client/utilities';
import { createClient } from 'graphql-ws';

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
 *   - RSC request (registerApolloClient calls this per request)
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
    // connectToDevTools is automatically disabled in production builds.
    connectToDevTools: process.env.NODE_ENV === 'development',
  });
}

// ---------------------------------------------------------------------------
// RSC client — for Server Component data fetching
// ---------------------------------------------------------------------------

/**
 * Register a per-request Apollo client for React Server Components.
 *
 * Usage in a Server Component:
 *   import { getClient } from '@/client/rsc-client';
 *   const { data } = await getClient().query({ query: MY_QUERY });
 *
 * Each RSC request gets its own cache — responses are not shared between users.
 */
export const { getClient } = registerApolloClient(makeClient);

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
 *   import { ApolloWrapper } from '@/client/apollo-client';
 *   <ApolloWrapper>{children}</ApolloWrapper>
 */
export { ApolloNextAppProvider as ApolloWrapper } from '@apollo/client-integration-nextjs';
