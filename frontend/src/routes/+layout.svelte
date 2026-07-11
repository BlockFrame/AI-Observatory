<script lang="ts">
	import { page } from '$app/stores';
	import '../app.css';
</script>

<div class="min-h-screen bg-[#0b1426] text-on-surface">
	<!-- Sidebar -->
	<aside class="fixed left-0 top-0 z-40 h-screen w-64 border-r border-[#2b3655] bg-[#111d33] shadow-2xl">
		<div class="flex h-full flex-col px-5 py-7">
			<div class="mb-10 flex items-center gap-4 px-2">
				<img src="/assets/logo.png" alt="AI Observatory Logo" class="h-14 w-14 rounded-lg object-cover" />
				<div class="min-w-0">
					<h1 class="text-5xl font-extrabold leading-none tracking-tight text-[#bfc2ff]">AI</h1>
					<p class="mt-1 whitespace-nowrap text-xs font-semibold uppercase tracking-[0.22em] text-[#8e94ae]">Observatory v2.4</p>
				</div>
			</div>

			<nav class="flex-1 space-y-2">
				<a href="/" class="flex items-center gap-4 px-4 py-4 {$page.url.pathname === '/' ? 'border-r-4 border-[#e4dcff] bg-[#4c4f81] text-[#d7daec]' : 'text-[#b2b8cf] hover:bg-[#2a3550] hover:text-[#d7daec]'}">
					<span class="material-symbols-outlined text-[22px]">dashboard</span>
					<span class="text-[17px] font-semibold tracking-[0.08em]">Dashboard</span>
				</a>
				<button class="flex w-full items-center gap-4 px-4 py-4 text-left text-[#b2b8cf] hover:bg-[#2a3550] hover:text-[#d7daec]" type="button">
					<span class="material-symbols-outlined text-[22px]">neurology</span>
					<span class="text-[17px] font-semibold tracking-[0.08em]">Models</span>
				</button>
				<a href="/feeds" class="flex items-center gap-4 px-4 py-4 {$page.url.pathname === '/feeds' ? 'border-r-4 border-[#e4dcff] bg-[#4c4f81] text-[#d7daec]' : 'text-[#b2b8cf] hover:bg-[#2a3550] hover:text-[#d7daec]'}">
					<span class="material-symbols-outlined text-[22px]">dynamic_feed</span>
					<span class="text-[17px] font-semibold tracking-[0.08em]">Neural Feed</span>
				</a>
				<button class="flex w-full items-center gap-4 px-4 py-4 text-left text-[#b2b8cf] hover:bg-[#2a3550] hover:text-[#d7daec]" type="button">
					<span class="material-symbols-outlined text-[22px]">error</span>
					<span class="text-[17px] font-semibold tracking-[0.08em]">Anomalies</span>
				</button>
				<button class="flex w-full items-center gap-4 px-4 py-4 text-left text-[#b2b8cf] hover:bg-[#2a3550] hover:text-[#d7daec]" type="button">
					<span class="material-symbols-outlined text-[22px]">account_tree</span>
					<span class="text-[17px] font-semibold tracking-[0.08em]">Architectures</span>
				</button>
				<button class="flex w-full items-center gap-4 px-4 py-4 text-left text-[#b2b8cf] hover:bg-[#2a3550] hover:text-[#d7daec]" type="button">
					<span class="material-symbols-outlined text-[22px]">settings</span>
					<span class="text-[17px] font-semibold tracking-[0.08em]">Settings</span>
				</button>
			</nav>
		</div>
	</aside>

	<!-- Header -->
	<header class="fixed left-64 right-0 top-0 z-30 border-b border-[#2b3655] bg-[#111d33]/80 backdrop-blur-md">
		<div class="flex h-16 items-center justify-between px-8">
			<div class="flex items-center gap-6">
				<div class="relative group">
					<span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-[#7d86a8] group-focus-within:text-[#c6cbff]">search</span>
					<input class="w-72 rounded-full border border-[#2b3655] bg-[#18243b] py-1.5 pl-10 pr-4 text-sm text-[#d8ddf4] placeholder:text-[#7d86a8] focus:border-[#7f88c4] focus:outline-none" placeholder="Scan neural network..." type="text" />
				</div>
			</div>
			<div class="flex items-center gap-4">
				<div class="flex items-center gap-2">
					<button class="p-2 text-[#b2b8cf] transition-colors hover:text-[#d8ddf4]" type="button"><span class="material-symbols-outlined">notifications</span></button>
					<button class="p-2 text-[#b2b8cf] transition-colors hover:text-[#d8ddf4]" type="button"><span class="material-symbols-outlined">help_outline</span></button>
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
