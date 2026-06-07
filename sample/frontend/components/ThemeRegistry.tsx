/**
 * MUI v9 ThemeRegistry for Next.js App Router.
 *
 * Provides Material UI theming with proper SSR cache support via
 * @mui/material-nextjs's AppRouterCacheProvider.
 *
 * MUI jumped from v7 to v9 — there is no v8. Key breaking change:
 *   Grid: <Grid xs={12} md={6} /> → <Grid size={{ xs: 12, md: 6 }} />
 *
 * Three layers (in order):
 *   1. AppRouterCacheProvider — prevents Emotion from re-inserting styles on
 *      each App Router navigation (avoids flash of unstyled content).
 *   2. ThemeProvider — provides the custom MUI theme to the component tree.
 *   3. CssBaseline — normalises browser default styles.
 *
 * Optional: add a light/dark mode toggle by storing the preferred mode in
 * a cookie (readable server-side to avoid SSR flicker) and passing it as
 * the `initialColorScheme` to createTheme.
 *
 * Usage in app/layout.tsx:
 *   import { ThemeRegistry } from '@/components/ThemeRegistry';
 *   <ThemeRegistry>{children}</ThemeRegistry>
 *
 * Required packages:
 *   @mui/material ^9.0.1
 *   @mui/material-nextjs ^9.0.1
 *   @emotion/react ^11
 *   @emotion/styled ^11
 */

'use client';

import CssBaseline from '@mui/material/CssBaseline';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { AppRouterCacheProvider } from '@mui/material-nextjs/v15-appRouter';
import React from 'react';

// ---------------------------------------------------------------------------
// Theme definition
// ---------------------------------------------------------------------------

/**
 * Custom MUI theme.
 *
 * `colorSchemes` enables MUI v9's built-in dark mode support.
 * Users can toggle with `useColorScheme()` from @mui/material/styles.
 */
const theme = createTheme({
  colorSchemes: {
    light: {
      palette: {
        primary: {
          main: '#1976d2',
        },
        background: {
          default: '#f5f5f5',
        },
      },
    },
    dark: {
      palette: {
        primary: {
          main: '#90caf9',
        },
        background: {
          default: '#121212',
          paper: '#1e1e1e',
        },
      },
    },
  },
  typography: {
    fontFamily: [
      'var(--font-geist-sans)',  // Next.js font variable — wire up in layout.tsx
      '-apple-system',
      'BlinkMacSystemFont',
      '"Segoe UI"',
      'sans-serif',
    ].join(','),
  },
  components: {
    // Example: override MuiButton to remove text transform globally
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
        },
      },
    },
  },
});

// ---------------------------------------------------------------------------
// ThemeRegistry component
// ---------------------------------------------------------------------------

interface ThemeRegistryProps {
  children: React.ReactNode;
}

/**
 * ThemeRegistry wraps the application with MUI SSR cache + theme + baseline.
 *
 * Place it in the root layout, inside any analytics or error boundary providers
 * but outside authentication guards so the theme applies universally.
 */
export function ThemeRegistry({ children }: ThemeRegistryProps): React.ReactElement {
  return (
    /*
     * AppRouterCacheProvider options:
     *   enableCssLayer: true — outputs MUI styles into a CSS @layer so your
     *   own styles can override MUI without !important.
     */
    <AppRouterCacheProvider options={{ enableCssLayer: true }}>
      <ThemeProvider theme={theme} defaultMode="system">
        {/* CssBaseline resets margins and applies the theme's background colour */}
        <CssBaseline />
        {children}
      </ThemeProvider>
    </AppRouterCacheProvider>
  );
}
