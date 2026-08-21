<script lang="ts">
	import { page } from '$app/stores';
	import { browser } from '$app/environment';
	import SearchBar from '$lib/components/search/SearchBar.svelte';
	import FeedbackModal from '$lib/components/FeedbackModal.svelte';
	import { SITE } from '$lib/site';
	import '../app.css';
	import { inject } from '@vercel/analytics';

	export let data: { latestDate: string | null };
	
	if (browser) inject();

	let isDesktopSidebarOpen = true;
	let isMobileNavOpen = false;
	let showScrollTop = false;
	let isFeedbackModalOpen = false;
	let activePath = '';
	$: currentSearch = browser ? $page.url.search : '';
	$: latestBase = data.latestDate ? `/briefings/${data.latestDate}` : '';
	$: if (browser && $page.url.pathname !== activePath) {
		activePath = $page.url.pathname;
		isMobileNavOpen = false;
	}

	function toggleSidebar() {
		if (browser && window.matchMedia('(min-width: 1024px)').matches) {
			isDesktopSidebarOpen = !isDesktopSidebarOpen;
		} else {
			isMobileNavOpen = !isMobileNavOpen;
		}
	}

	function handleScroll() {
		showScrollTop = window.scrollY > 300;
	}

	function scrollToTop() {
		window.scrollTo({ top: 0, behavior: 'smooth' });
	}
</script>

<svelte:window on:scroll={handleScroll} />
<svelte:body class:overflow-hidden={isMobileNavOpen} />

<div class="min-h-screen bg-[#0b1426] text-on-surface">
	{#if isMobileNavOpen}
		<button
			type="button"
			class="fixed inset-0 z-[35] bg-[#050a14]/75 backdrop-blur-sm lg:hidden"
			on:click={() => (isMobileNavOpen = false)}
			aria-label="Close navigation"
		></button>
	{/if}

	<!-- Sidebar -->
	<aside class="fixed left-0 top-0 z-40 h-screen w-64 overflow-x-hidden overflow-y-auto border-r border-white/10 bg-[#0c1322]/95 shadow-2xl backdrop-blur-xl transition-transform duration-300 {isMobileNavOpen ? 'translate-x-0' : '-translate-x-full'} {isDesktopSidebarOpen ? 'lg:translate-x-0' : 'lg:-translate-x-full'}">
		<div class="flex h-full flex-col px-4 py-6">
			<div class="mb-5 flex items-center justify-between lg:hidden">
				<a href="/" class="flex items-center gap-2 text-sm font-semibold tracking-[0.04em] text-[#00e0bb]">
					<img src="/logo.png" alt="" class="h-7 w-7 rounded-sm object-contain" />
					<span>R<span class="text-[#cfd5ff]">[AI]</span>DAR</span>
				</a>
				<button
					type="button"
					on:click={() => (isMobileNavOpen = false)}
					class="flex h-10 w-10 items-center justify-center rounded-lg text-[#b2b8cf] hover:bg-white/5 hover:text-white"
					aria-label="Close navigation"
				>
					<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18M6 6l12 12"/></svg>
				</button>
			</div>

			<nav class="flex-1">
				<p class="mb-3 px-3 text-[10px] font-medium uppercase tracking-[0.14em] text-[#8e94ae]">Navigation</p>
				<div class="space-y-1.5">
				<a href="/" class="flex min-h-[44px] items-center rounded-lg px-4 py-2.5 transition-all duration-200 {$page.url.pathname === '/' && !currentSearch.includes('category=') ? 'border-r-2 border-[#9aa6ff] bg-[#232a3a] text-[#cfd5ff] shadow-[inset_0_0_0_1px_rgba(154,166,255,0.2)]' : 'text-[#b2b8cf] hover:bg-[#1b2437] hover:text-[#d8ddf4]'}">
					<span class="text-[13px] font-medium tracking-[0.02em]">Home</span>
				</a>
				<a href={latestBase ? `${latestBase}/news` : '/archive'} class="flex min-h-[44px] items-center rounded-lg px-4 py-2.5 transition-all duration-200 {$page.url.pathname.endsWith('/news') || currentSearch.includes('category=news') ? 'border-r-2 border-[#9aa6ff] bg-[#232a3a] text-[#cfd5ff] shadow-[inset_0_0_0_1px_rgba(154,166,255,0.2)]' : 'text-[#b2b8cf] hover:bg-[#1b2437] hover:text-[#d8ddf4]'}">
					<span class="text-[13px] font-medium tracking-[0.02em]">AI News</span>
				</a>
				<a href={latestBase ? `${latestBase}/research` : '/archive'} class="flex min-h-[44px] items-center rounded-lg px-4 py-2.5 transition-all duration-200 {$page.url.pathname.endsWith('/research') || currentSearch.includes('category=research') ? 'border-r-2 border-[#9aa6ff] bg-[#232a3a] text-[#cfd5ff] shadow-[inset_0_0_0_1px_rgba(154,166,255,0.2)]' : 'text-[#b2b8cf] hover:bg-[#1b2437] hover:text-[#d8ddf4]'}">
					<span class="text-[13px] font-medium tracking-[0.02em]">Research</span>
				</a>
				<a href={latestBase ? `${latestBase}/social` : '/archive'} class="flex min-h-[44px] items-center rounded-lg px-4 py-2.5 transition-all duration-200 {$page.url.pathname.endsWith('/social') || currentSearch.includes('category=social') ? 'border-r-2 border-[#9aa6ff] bg-[#232a3a] text-[#cfd5ff] shadow-[inset_0_0_0_1px_rgba(154,166,255,0.2)]' : 'text-[#b2b8cf] hover:bg-[#1b2437] hover:text-[#d8ddf4]'}">
					<span class="text-[13px] font-medium tracking-[0.02em]">Social Media</span>
				</a>

                <a href={latestBase ? `${latestBase}/github_trending` : '/archive'} class="flex min-h-[44px] items-center rounded-lg px-4 py-2.5 transition-all duration-200 {$page.url.pathname.endsWith('/github_trending') || currentSearch.includes('category=github_trending') ? 'border-r-2 border-[#9aa6ff] bg-[#232a3a] text-[#cfd5ff] shadow-[inset_0_0_0_1px_rgba(154,166,255,0.2)]' : 'text-[#b2b8cf] hover:bg-[#1b2437] hover:text-[#d8ddf4]'}">
                    <span class="text-[13px] font-medium tracking-[0.02em]">GitHub Trending</span>
                </a>

                <a href="/models" class="flex min-h-[44px] items-center rounded-lg px-4 py-2.5 transition-all duration-200 {$page.url.pathname === '/models' ? 'border-r-2 border-[#9aa6ff] bg-[#232a3a] text-[#cfd5ff] shadow-[inset_0_0_0_1px_rgba(154,166,255,0.2)]' : 'text-[#b2b8cf] hover:bg-[#1b2437] hover:text-[#d8ddf4]'}">
                    <span class="text-[13px] font-medium tracking-[0.02em]">Models Directory</span>
                </a>
                <a href="/tools" class="flex min-h-[44px] items-center rounded-lg px-4 py-2.5 transition-all duration-200 {$page.url.pathname === '/tools' ? 'border-r-2 border-[#9aa6ff] bg-[#232a3a] text-[#cfd5ff] shadow-[inset_0_0_0_1px_rgba(154,166,255,0.2)]' : 'text-[#b2b8cf] hover:bg-[#1b2437] hover:text-[#d8ddf4]'}">
                    <span class="text-[13px] font-medium tracking-[0.02em]">Tools Directory</span>
                </a>
                <a href="/influencers" class="flex min-h-[44px] items-center rounded-lg px-4 py-2.5 transition-all duration-200 {$page.url.pathname === '/influencers' ? 'border-r-2 border-[#9aa6ff] bg-[#232a3a] text-[#cfd5ff] shadow-[inset_0_0_0_1px_rgba(154,166,255,0.2)]' : 'text-[#b2b8cf] hover:bg-[#1b2437] hover:text-[#d8ddf4]'}">
                    <span class="text-[13px] font-medium tracking-[0.02em]">Influencers</span>
                </a>
				<a href="/archive" class="flex min-h-[44px] items-center rounded-lg px-4 py-2.5 transition-all duration-200 {$page.url.pathname === '/archive' ? 'border-r-2 border-[#9aa6ff] bg-[#232a3a] text-[#cfd5ff] shadow-[inset_0_0_0_1px_rgba(154,166,255,0.2)]' : 'text-[#b2b8cf] hover:bg-[#1b2437] hover:text-[#d8ddf4]'}">
					<span class="text-[13px] font-medium tracking-[0.02em]">Archive</span>
				</a>
				<a href="/about" class="flex min-h-[44px] items-center rounded-lg px-4 py-2.5 transition-all duration-200 {$page.url.pathname === '/about' ? 'border-r-2 border-[#9aa6ff] bg-[#232a3a] text-[#cfd5ff] shadow-[inset_0_0_0_1px_rgba(154,166,255,0.2)]' : 'text-[#b2b8cf] hover:bg-[#1b2437] hover:text-[#d8ddf4]'}">
					<span class="text-[13px] font-medium tracking-[0.02em]">About</span>
				</a>
				<a href="https://github.com/sponsors/BlockFrame" target="_blank" rel="noopener noreferrer" class="flex min-h-[44px] items-center rounded-lg px-4 py-2.5 transition-all duration-200 text-[#ff79c6] hover:bg-[#ff79c6]/10 hover:text-white mt-4 border border-[#ff79c6]/20">
					<span class="text-[13px] font-medium tracking-[0.02em] flex items-center gap-2">
						<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>
						Sponsor Project
					</span>
				</a>
				</div>
			</nav>
		</div>
	</aside>

	<!-- Header -->
	<header class="fixed left-0 right-0 top-0 z-30 border-b border-[#2b3655] bg-[#111d33]/90 backdrop-blur-md transition-all duration-300 {isDesktopSidebarOpen ? 'lg:left-64' : 'lg:left-0'}">
		<div class="flex h-16 items-center justify-between gap-3 px-3 sm:px-4 md:px-8">
			<div class="flex min-w-0 items-center gap-2 sm:gap-4">
				<button type="button" on:click={toggleSidebar} class="p-2 -ml-2 text-[#8e94ae] hover:text-white rounded-lg hover:bg-[#2b3655]/50 transition-colors" aria-label="Toggle Navigation">
					<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h16M4 12h16M4 18h16"/></svg>
				</button>
				<div class="hidden min-w-0 items-center lg:flex">
					<div class="w-[clamp(16rem,38vw,42rem)] max-w-full">
						<SearchBar placeholder="Search news, research, social and repositories…" />
					</div>
				</div>
				<a href="/" class="flex min-w-0 items-center gap-2 lg:hidden" aria-label={SITE.name}>
					<img src="/logo.png" alt="" class="h-7 w-7 shrink-0 rounded-sm object-contain" />
					<span class="truncate text-[13px] font-semibold tracking-[0.04em] text-[#00e0bb] sm:text-sm">
						R<span class="text-[#cfd5ff]">[AI]</span>DAR
					</span>
				</a>
			</div>

			<div class="flex shrink-0 items-center gap-1 sm:gap-2 lg:gap-4">
				<!-- Sponsor Button -->
				<a
					href="https://github.com/sponsors/BlockFrame"
					target="_blank"
					rel="noopener noreferrer"
					class="hidden items-center gap-1.5 rounded-lg border border-[#ff79c6]/30 bg-[#ff79c6]/10 px-3 py-1.5 text-sm font-medium text-[#ff79c6] transition-all hover:bg-[#ff79c6] hover:text-white md:flex"
					aria-label="Sponsor on GitHub"
					title="Sponsor Wiredframe Radar on GitHub"
				>
					<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>
					<span>Sponsor</span>
				</a>

				<!-- Feedback Button -->
				<button
					type="button"
					on:click={() => isFeedbackModalOpen = true}
					class="flex h-10 w-10 items-center justify-center rounded-lg border border-[#2b3655] bg-[#1b2437] text-[#b2b8cf] transition-all hover:bg-[#2b3655] hover:text-white sm:h-auto sm:w-auto sm:gap-2 sm:px-3 sm:py-1.5"
					aria-label="Feedback"
				>
					<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
					<span class="hidden md:inline">Feedback</span>
				</button>

				<!-- GitHub icon -->
				<a
					href={SITE.githubUrl}
					target="_blank"
					rel="noopener noreferrer"
					class="flex h-10 w-10 items-center justify-center rounded-lg text-[#b2b8cf] transition-colors hover:bg-[#2b3655]/50 hover:text-white"
					aria-label="GitHub Repository"
					title="View source on GitHub"
				>
					<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
						<path fill-rule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" clip-rule="evenodd" />
					</svg>
				</a>

				<div class="hidden h-6 w-px bg-white/10 lg:block"></div>

				<img src="/logo.png" alt="Wiredframe Radar logo" class="hidden h-6 w-6 shrink-0 rounded-sm object-contain lg:block" />
				<div class="hidden min-w-0 overflow-hidden lg:block">
					<a href="/" class="block truncate text-[15px] font-semibold tracking-[0.04em] text-[#00e0bb]" aria-label={SITE.name}>
						R<span class="text-[#cfd5ff]">[AI]</span>DAR
					</a>
				</div>
			</div>
		</div>
		<div class="border-t border-white/5 px-3 pb-3 pt-2 lg:hidden">
			<SearchBar placeholder="Search Radar…" />
		</div>
	</header>

	<!-- Main Content -->
	<main class="min-h-screen px-3 pt-36 transition-all duration-300 sm:px-4 md:px-8 lg:pt-24 {isDesktopSidebarOpen ? 'lg:ml-64' : 'lg:ml-0'}">
		<slot />
	</main>

	<!-- Scroll To Top Button -->
	{#if showScrollTop}
		<button
			type="button"
			on:click={scrollToTop}
			class="fixed bottom-6 right-6 z-50 flex h-11 w-11 items-center justify-center rounded-full border border-white/20 bg-[#111d33]/90 text-[#00e0bb] shadow-xl backdrop-blur-md transition-all duration-300 hover:border-[#00e0bb] hover:bg-[#00e0bb] hover:text-[#0b1426] hover:scale-110 active:scale-95"
			aria-label="Scroll to top"
			title="Torna su"
		>
			<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
				<path d="m18 15-6-6-6 6"/>
			</svg>
		</button>
	{/if}

</div>

<FeedbackModal bind:isOpen={isFeedbackModalOpen} />

<svelte:head>
	<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet" />
	{@html `<script type="application/ld+json">${JSON.stringify({
		'@context': 'https://schema.org',
		'@type': 'WebSite',
		name: SITE.name,
		alternateName: SITE.visualName,
		url: SITE.url,
		description: SITE.description,
		publisher: {
			'@type': 'Organization',
			name: SITE.parentName,
			url: SITE.parentUrl
		}
	})}<\/script>`}
</svelte:head>
