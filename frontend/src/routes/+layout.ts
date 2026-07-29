// Disable SSR for the entire app — this is a static SPA.
// Without this, refreshing on /tools or /models causes SvelteKit 
// to attempt server-side rendering which fails because these pages
// fetch data client-side in onMount().
export const ssr = false;
