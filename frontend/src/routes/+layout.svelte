<script lang="ts">
	import { page } from '$app/stores';
	import { browser } from '$app/environment';
	import '../app.css';

	let sidebarOpen = browser && window.innerWidth >= 768;
</script>

<div class="min-h-screen bg-background text-on-surface">
	<!-- Sidebar -->
	<aside class="fixed h-screen left-0 top-0 w-64 flex flex-col bg-surface-glass backdrop-blur-xl border-r border-outline-variant/20 shadow-2xl z-50" style="background: rgba(31, 41, 55, 0.6);">
		<div class="flex flex-col h-full py-6 px-4">
			<div class="flex items-center gap-3 mb-10 px-2">
				<div class="w-10 h-10 rounded-lg bg-primary/30 flex items-center justify-center">
					<span class="font-headline-lg text-primary-fixed-dim font-bold">AI</span>
				</div>
				<div>
					<h1 class="font-headline-lg text-headline-lg font-bold text-primary-fixed-dim">Observatory</h1>
					<p class="font-label-caps text-[10px] text-outline uppercase">v2.4</p>
				</div>
			</div>
			
			<nav class="flex-1 space-y-1">
				<a href="/" class="flex items-center gap-3 px-3 py-3 {$page.url.pathname === '/' ? 'text-primary bg-primary-container/20 border-r-4 border-primary' : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-variant/30'} transition-all duration-300">
					<span class="material-symbols-outlined">dashboard</span>
					<span class="font-label-caps text-label-caps">Dashboard</span>
				</a>
				<a href="/feeds" class="flex items-center gap-3 px-3 py-3 {$page.url.pathname === '/feeds' ? 'text-primary bg-primary-container/20 border-r-4 border-primary' : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-variant/30'} transition-all duration-300">
					<span class="material-symbols-outlined">dynamic_feed</span>
					<span class="font-label-caps text-label-caps">Neural Feed</span>
				</a>
				<a href="/archive" class="flex items-center gap-3 px-3 py-3 {$page.url.pathname === '/archive' ? 'text-primary bg-primary-container/20 border-r-4 border-primary' : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-variant/30'} transition-all duration-300">
					<span class="material-symbols-outlined">history</span>
					<span class="font-label-caps text-label-caps">Archive</span>
				</a>
				<a href="/about" class="flex items-center gap-3 px-3 py-3 {$page.url.pathname === '/about' ? 'text-primary bg-primary-container/20 border-r-4 border-primary' : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-variant/30'} transition-all duration-300">
					<span class="material-symbols-outlined">info</span>
					<span class="font-label-caps text-label-caps">About</span>
				</a>
			</nav>
			
			<div class="mt-auto pt-6 border-t border-outline-variant/10">
				<button class="w-full bg-primary text-on-primary py-3 rounded-lg font-label-caps text-label-caps hover:brightness-110 transition-all shadow-lg shadow-primary/20 mb-4" type="button">
					Deploy Agent
				</button>
				<div class="space-y-1">
					<button class="flex items-center gap-3 px-3 py-2 text-on-surface-variant hover:text-on-surface text-sm w-full" type="button">
						<span class="material-symbols-outlined text-sm">menu_book</span>
						<span class="font-label-caps text-[12px]">Docs</span>
					</button>
					<button class="flex items-center gap-3 px-3 py-2 text-on-surface-variant hover:text-on-surface text-sm w-full" type="button">
						<span class="material-symbols-outlined text-sm">logout</span>
						<span class="font-label-caps text-[12px]">Logout</span>
					</button>
				</div>
			</div>
		</div>
	</aside>

	<!-- Header -->
	<header class="fixed top-0 w-full z-40 bg-surface-glass/80 backdrop-blur-md border-b border-outline-variant/10 shadow-sm ml-64" style="background: rgba(31, 41, 55, 0.8);">
		<div class="flex items-center justify-between h-16 px-gutter">
			<div class="flex items-center gap-6">
				<div class="relative group">
					<span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline group-focus-within:text-primary">search</span>
					<input class="bg-surface-container-low border-none rounded-full pl-10 pr-4 py-1.5 text-sm w-64 focus:ring-1 focus:ring-primary text-on-surface placeholder:text-outline-variant" placeholder="Scan neural network..." type="text"/>
				</div>
			</div>
			<div class="flex items-center gap-4">
				<button class="bg-surface-container-high hover:bg-surface-container-highest px-4 py-2 rounded-lg text-primary text-sm font-semibold flex items-center gap-2 border border-primary/20" type="button">
					<span class="material-symbols-outlined text-sm">terminal</span>
					Execute Prompt
				</button>
				<div class="flex items-center gap-2">
					<button class="p-2 hover:text-primary transition-colors" type="button"><span class="material-symbols-outlined">notifications</span></button>
					<button class="p-2 hover:text-primary transition-colors" type="button"><span class="material-symbols-outlined">help_outline</span></button>
				</div>
			</div>
		</div>
	</header>

	<!-- Main Content -->
	<main class="ml-64 pt-20 p-gutter max-w-[1440px] mx-auto min-h-screen">
		<slot />
	</main>

	<!-- FAB -->
	<button class="fixed bottom-8 right-8 w-16 h-16 rounded-full bg-primary text-on-primary flex items-center justify-center shadow-2xl shadow-primary/40 hover:scale-110 transition-transform z-40" type="button">
		<span class="material-symbols-outlined text-3xl">psychiatry</span>
	</button>
</div>

<svelte:head>
	<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet" />
</svelte:head>
