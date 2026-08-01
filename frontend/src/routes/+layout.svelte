<script lang="ts">
	import { page } from '$app/stores';
	import SearchBar from '$lib/components/search/SearchBar.svelte';
	import '../app.css';
	import { inject } from '@vercel/analytics';
	
	inject();

	let isSidebarOpen = true;
	let showScrollTop = false;

	function toggleSidebar() {
		isSidebarOpen = !isSidebarOpen;
	}

	function handleScroll() {
		showScrollTop = window.scrollY > 300;
	}

	function scrollToTop() {
		window.scrollTo({ top: 0, behavior: 'smooth' });
	}
</script>

<svelte:window on:scroll={handleScroll} />

<div class="min-h-screen bg-[#0b1426] text-on-surface">
	<!-- Sidebar -->
	<aside class="fixed left-0 top-0 z-40 h-screen overflow-hidden border-r border-white/10 bg-[#0c1322]/80 shadow-2xl backdrop-blur-xl transition-all duration-300 {isSidebarOpen ? 'w-64 translate-x-0' : 'w-64 -translate-x-full'}">
		<div class="flex h-full flex-col px-4 py-6">

			<nav class="flex-1">
				<p class="mb-3 px-3 text-[10px] font-medium uppercase tracking-[0.14em] text-[#8e94ae]">Navigation</p>
				<div class="space-y-1.5">
				<a href="/" class="flex min-h-[44px] items-center rounded-lg px-4 py-2.5 transition-all duration-200 {$page.url.pathname === '/' && !$page.url.search.includes('category=') ? 'border-r-2 border-[#9aa6ff] bg-[#232a3a] text-[#cfd5ff] shadow-[inset_0_0_0_1px_rgba(154,166,255,0.2)]' : 'text-[#b2b8cf] hover:bg-[#1b2437] hover:text-[#d8ddf4]'}">
					<span class="text-[13px] font-medium tracking-[0.02em]">Home</span>
				</a>
				<a href="/?category=news" class="flex min-h-[44px] items-center rounded-lg px-4 py-2.5 transition-all duration-200 {$page.url.pathname === '/' && $page.url.search.includes('category=news') ? 'border-r-2 border-[#9aa6ff] bg-[#232a3a] text-[#cfd5ff] shadow-[inset_0_0_0_1px_rgba(154,166,255,0.2)]' : 'text-[#b2b8cf] hover:bg-[#1b2437] hover:text-[#d8ddf4]'}">
					<span class="text-[13px] font-medium tracking-[0.02em]">AI News</span>
				</a>
				<a href="/?category=research" class="flex min-h-[44px] items-center rounded-lg px-4 py-2.5 transition-all duration-200 {$page.url.pathname === '/' && $page.url.search.includes('category=research') ? 'border-r-2 border-[#9aa6ff] bg-[#232a3a] text-[#cfd5ff] shadow-[inset_0_0_0_1px_rgba(154,166,255,0.2)]' : 'text-[#b2b8cf] hover:bg-[#1b2437] hover:text-[#d8ddf4]'}">
					<span class="text-[13px] font-medium tracking-[0.02em]">Research</span>
				</a>
				<a href="/?category=social" class="flex min-h-[44px] items-center rounded-lg px-4 py-2.5 transition-all duration-200 {$page.url.pathname === '/' && $page.url.search.includes('category=social') ? 'border-r-2 border-[#9aa6ff] bg-[#232a3a] text-[#cfd5ff] shadow-[inset_0_0_0_1px_rgba(154,166,255,0.2)]' : 'text-[#b2b8cf] hover:bg-[#1b2437] hover:text-[#d8ddf4]'}">
					<span class="text-[13px] font-medium tracking-[0.02em]">Social Media</span>
				</a>

                <a href="/?category=github_trending" class="flex min-h-[44px] items-center rounded-lg px-4 py-2.5 transition-all duration-200 {$page.url.pathname === '/' && $page.url.search.includes('category=github_trending') ? 'border-r-2 border-[#9aa6ff] bg-[#232a3a] text-[#cfd5ff] shadow-[inset_0_0_0_1px_rgba(154,166,255,0.2)]' : 'text-[#b2b8cf] hover:bg-[#1b2437] hover:text-[#d8ddf4]'}">
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
				</div>
			</nav>
		</div>
	</aside>

	<!-- Header -->
	<header class="fixed right-0 top-0 z-30 border-b border-[#2b3655] bg-[#111d33]/80 backdrop-blur-md transition-all duration-300 {isSidebarOpen ? 'left-64' : 'left-0'}">
		<div class="flex h-16 items-center justify-between px-4 md:px-8 gap-4">
			<div class="flex items-center gap-4">
				<button on:click={toggleSidebar} class="p-2 -ml-2 text-[#8e94ae] hover:text-white rounded-lg hover:bg-[#2b3655]/50 transition-colors" aria-label="Toggle Navigation">
					{#if isSidebarOpen}
						<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><path d="M9 3v18"/><path d="m16 15-3-3 3-3"/></svg>
					{:else}
						<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><path d="M9 3v18"/><path d="m14 9 3 3-3 3"/></svg>
					{/if}
				</button>
				<div class="flex items-center">
					<div class="w-64 md:w-80">
						<SearchBar placeholder="Search..." />
					</div>
				</div>
			</div>

			<div class="flex items-center gap-2">
				<img src="/logo.png" alt="AI Observatory Logo" class="h-6 w-6 shrink-0 rounded-sm object-contain" />
				<div class="min-w-0 overflow-hidden hidden sm:block">
					<h1 class="truncate text-[15px] font-semibold tracking-[0.02em] text-[#00e0bb]">
						AI Observatory <span class="text-[11px] font-medium uppercase tracking-[0.12em] text-[#8e94ae]">v2.4</span>
					</h1>
				</div>
			</div>
		</div>
	</header>

	<!-- Main Content -->
	<main class="min-h-screen px-4 md:px-8 pt-24 transition-all duration-300 {isSidebarOpen ? 'ml-64' : 'ml-0'}">
		<slot />
	</main>

	<!-- Scroll To Top Button -->
	{#if showScrollTop}
		<button
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

<svelte:head>
	<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet" />
</svelte:head>
