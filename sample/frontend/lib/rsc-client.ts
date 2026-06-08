/**
 * Apollo Client for React Server Components (RSC).
 *
 * This file has NO 'use client' directive — it runs exclusively on the server.
 * Importing it in a Client Component will cause a build error.
 *
 * registerApolloClient creates a per-request client so RSC responses are never
 * shared between concurrent user requests.
 *
 * Usage in a Server Component:
 *   import { getClient } from '@/lib/rsc-client';
 *   const { data } = await getClient().query({ query: MY_QUERY });
 *
 * For Client Components (useQuery, useSuspenseQuery, useSubscription), use
 * ApolloWrapper from lib/apollo-client.ts instead.
 */

import { registerApolloClient } from '@apollo/client-integration-nextjs';

import { makeClient } from './apollo-client';

export const { getClient } = registerApolloClient(makeClient);
