<script lang="ts">
	import { page } from '$app/stores';
	import SearchBar from '$lib/components/search/SearchBar.svelte';
	import '../app.css';
</script>

<div class="min-h-screen bg-[#0b1426] text-on-surface">
	<!-- Sidebar -->
	<aside class="fixed left-0 top-0 z-40 h-screen w-64 overflow-hidden border-r border-white/10 bg-[#0c1322]/80 shadow-2xl backdrop-blur-xl">
		<div class="flex h-full flex-col px-4 py-6">
			<div class="mb-8 flex items-center gap-2 px-2">
				<img src="/logo.png" alt="AI Observatory Logo" class="h-6 w-6 shrink-0 rounded-sm object-contain" />
				<div class="min-w-0 max-w-[165px] overflow-hidden">
					<h1 class="truncate text-[15px] font-semibold tracking-[0.02em] text-[#00e0bb]">
						AI Observatory <span class="text-[11px] font-medium uppercase tracking-[0.12em] text-[#8e94ae]">v2.4</span>
					</h1>
				</div>
			</div>

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
				<a href="/?category=reddit" class="flex min-h-[44px] items-center rounded-lg px-4 py-2.5 transition-all duration-200 {$page.url.pathname === '/' && $page.url.search.includes('category=reddit') ? 'border-r-2 border-[#9aa6ff] bg-[#232a3a] text-[#cfd5ff] shadow-[inset_0_0_0_1px_rgba(154,166,255,0.2)]' : 'text-[#b2b8cf] hover:bg-[#1b2437] hover:text-[#d8ddf4]'}">
					<span class="text-[13px] font-medium tracking-[0.02em]">Reddit Discussions</span>
				</a>
                <a href="/?category=github_trending" class="flex min-h-[44px] items-center rounded-lg px-4 py-2.5 transition-all duration-200 {$page.url.pathname === '/' && $page.url.search.includes('category=github_trending') ? 'border-r-2 border-[#9aa6ff] bg-[#232a3a] text-[#cfd5ff] shadow-[inset_0_0_0_1px_rgba(154,166,255,0.2)]' : 'text-[#b2b8cf] hover:bg-[#1b2437] hover:text-[#d8ddf4]'}">
                    <span class="text-[13px] font-medium tracking-[0.02em]">GitHub Trending</span>
                </a>
				<a href="/feeds" class="flex min-h-[44px] items-center rounded-lg px-4 py-2.5 transition-all duration-200 {$page.url.pathname === '/feeds' ? 'border-r-2 border-[#9aa6ff] bg-[#232a3a] text-[#cfd5ff] shadow-[inset_0_0_0_1px_rgba(154,166,255,0.2)]' : 'text-[#b2b8cf] hover:bg-[#1b2437] hover:text-[#d8ddf4]'}">
					<span class="text-[13px] font-medium tracking-[0.02em]">RSS Feed</span>
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
	<header class="fixed left-64 right-0 top-0 z-30 border-b border-[#2b3655] bg-[#111d33]/80 backdrop-blur-md">
		<div class="flex h-16 items-center px-8">
			<div class="flex items-center">
				<div class="w-80">
					<SearchBar placeholder="Search..." />
				</div>
			</div>
		</div>
	</header>

	<!-- Main Content -->
	<main class="ml-64 min-h-screen px-8 pt-24">
		<slot />
	</main>

</div>

<svelte:head>
	<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet" />
</svelte:head>
