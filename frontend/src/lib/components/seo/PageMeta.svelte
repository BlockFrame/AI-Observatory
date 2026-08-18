<script lang="ts">
	import { SITE, absoluteUrl } from '$lib/config/site';

	let {
		title,
		description = SITE.description,
		path = '/',
		type = 'website',
		image = SITE.imagePath,
		noindex = false
	}: {
		title?: string;
		description?: string;
		path?: string;
		type?: string;
		image?: string;
		noindex?: boolean;
	} = $props();

	let pageTitle = $derived(title ? `${title} | ${SITE.name}` : `${SITE.name} | Daily AI Intelligence`);
	let canonical = $derived(absoluteUrl(path));
	let socialImage = $derived(image.startsWith('http') ? image : absoluteUrl(image));
</script>

<svelte:head>
	<title>{pageTitle}</title>
	<meta name="description" content={description} />
	<meta name="robots" content={noindex ? 'noindex,follow' : 'index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1'} />
	<link rel="canonical" href={canonical} />

	<meta property="og:type" content={type} />
	<meta property="og:site_name" content={SITE.name} />
	<meta property="og:url" content={canonical} />
	<meta property="og:title" content={pageTitle} />
	<meta property="og:description" content={description} />
	<meta property="og:image" content={socialImage} />

	<meta name="twitter:card" content="summary" />
	<meta name="twitter:title" content={pageTitle} />
	<meta name="twitter:description" content={description} />
	<meta name="twitter:image" content={socialImage} />
</svelte:head>

