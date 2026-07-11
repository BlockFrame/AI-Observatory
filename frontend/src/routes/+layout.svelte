<script lang="ts">
	import { page } from '$app/stores';
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

			<nav class="flex-1 space-y-2">
				<a href="/" class="flex items-center rounded-md px-3 py-2.5 transition-all duration-200 {$page.url.pathname === '/' && !$page.url.search.includes('category=') ? 'border-r-2 border-[#9aa6ff] bg-white/10 text-[#bfc2ff]' : 'text-[#b2b8cf] hover:bg-white/10 hover:text-[#d8ddf4]'}">
					<span class="text-[12px] font-semibold uppercase tracking-wider">Home</span>
				</a>
				<a href="/?category=news" class="flex items-center rounded-md px-3 py-2.5 transition-all duration-200 {$page.url.pathname === '/' && $page.url.search.includes('category=news') ? 'border-r-2 border-[#9aa6ff] bg-white/10 text-[#bfc2ff]' : 'text-[#b2b8cf] hover:bg-white/10 hover:text-[#d8ddf4]'}">
					<span class="text-[12px] font-semibold uppercase tracking-wider">AI News</span>
				</a>
				<a href="/?category=research" class="flex items-center rounded-md px-3 py-2.5 transition-all duration-200 {$page.url.pathname === '/' && $page.url.search.includes('category=research') ? 'border-r-2 border-[#9aa6ff] bg-white/10 text-[#bfc2ff]' : 'text-[#b2b8cf] hover:bg-white/10 hover:text-[#d8ddf4]'}">
					<span class="text-[12px] font-semibold uppercase tracking-wider">Research</span>
				</a>
				<a href="/?category=social" class="flex items-center rounded-md px-3 py-2.5 transition-all duration-200 {$page.url.pathname === '/' && $page.url.search.includes('category=social') ? 'border-r-2 border-[#9aa6ff] bg-white/10 text-[#bfc2ff]' : 'text-[#b2b8cf] hover:bg-white/10 hover:text-[#d8ddf4]'}">
					<span class="text-[12px] font-semibold uppercase tracking-wider">Social Media</span>
				</a>
				<a href="/?category=reddit" class="flex items-center rounded-md px-3 py-2.5 transition-all duration-200 {$page.url.pathname === '/' && $page.url.search.includes('category=reddit') ? 'border-r-2 border-[#9aa6ff] bg-white/10 text-[#bfc2ff]' : 'text-[#b2b8cf] hover:bg-white/10 hover:text-[#d8ddf4]'}">
					<span class="text-[12px] font-semibold uppercase tracking-wider">Reddit Discussions</span>
				</a>
				<a href="/feeds" class="flex items-center rounded-md px-3 py-2.5 transition-all duration-200 {$page.url.pathname === '/feeds' ? 'border-r-2 border-[#9aa6ff] bg-white/10 text-[#bfc2ff]' : 'text-[#b2b8cf] hover:bg-white/10 hover:text-[#d8ddf4]'}">
					<span class="text-[12px] font-semibold uppercase tracking-wider">RSS Feed</span>
				</a>
				<a href="/archive" class="flex items-center rounded-md px-3 py-2.5 transition-all duration-200 {$page.url.pathname === '/archive' ? 'border-r-2 border-[#9aa6ff] bg-white/10 text-[#bfc2ff]' : 'text-[#b2b8cf] hover:bg-white/10 hover:text-[#d8ddf4]'}">
					<span class="text-[12px] font-semibold uppercase tracking-wider">Archive</span>
				</a>
				<a href="/about" class="flex items-center rounded-md px-3 py-2.5 transition-all duration-200 {$page.url.pathname === '/about' ? 'border-r-2 border-[#9aa6ff] bg-white/10 text-[#bfc2ff]' : 'text-[#b2b8cf] hover:bg-white/10 hover:text-[#d8ddf4]'}">
					<span class="text-[12px] font-semibold uppercase tracking-wider">About</span>
				</a>
			</nav>
		</div>
	</aside>

	<!-- Header -->
	<header class="fixed left-64 right-0 top-0 z-30 border-b border-[#2b3655] bg-[#111d33]/80 backdrop-blur-md">
		<div class="flex h-16 items-center px-8">
			<div class="flex items-center">
				<input class="w-72 rounded-full border border-[#2b3655] bg-[#18243b] px-4 py-2 text-sm text-[#d8ddf4] placeholder:text-[#7d86a8] focus:border-[#7f88c4] focus:outline-none" placeholder="Search..." type="text" />
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
