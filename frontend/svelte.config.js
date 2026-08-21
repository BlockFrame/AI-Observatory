import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

const allowEmptyReportData = process.env.RAIDAR_ALLOW_EMPTY_REPORT_DATA === 'true';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),

	kit: {
		adapter: adapter({
			pages: '../web',
			assets: '../web',
			precompress: false,
			strict: true
		}),
		paths: {
			base: '',
			relative: false
		},
		prerender: {
			// Dynamic model routes are enumerated from models.json. Do not follow
			// historical cross-links in rich model content into obsolete aliases.
			crawl: false,
			// Docker images are built without the 900 MB historical report archive;
			// the runtime bind mount supplies it. Vercel and local release builds
			// remain strict and fail if configured dynamic routes go missing.
			handleUnseenRoutes: allowEmptyReportData ? 'ignore' : 'fail',
			handleHttpError: ({ path, referrer, message }) => {
				// Ignore 404s for /data/ paths - these are runtime files, not built
				if (path.startsWith('/data/')) {
					return;
				}
				// Throw for all other errors
				throw new Error(message);
			}
		},
		// script-src gets per-page 'sha256-…' hashes for SvelteKit's inline hydration
		// script at build time; frame-ancestors is auto-omitted from the <meta> tag by
		// SvelteKit and enforced by the nginx header instead.
		csp: {
			mode: 'hash',
			directives: {
				'default-src': ['self'],
				'script-src': ['self'],
				'style-src': ['self', 'unsafe-inline'],
				'img-src': ['self', 'data:'],
				'font-src': ['self'],
				'connect-src': ['self'],
				'worker-src': ['self'],
				'object-src': ['none'],
				'base-uri': ['self'],
				'frame-ancestors': ['self']
			}
		}
	}
};

export default config;
