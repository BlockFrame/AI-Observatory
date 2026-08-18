<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { goto } from '$app/navigation';
	import type { Category, NewsItem } from '$lib/types';
	import { peekItem, resolveItem } from '$lib/services/itemIndex';
	import { isSafeUrl } from '$lib/services/sanitize';
	import { portal } from '$lib/actions/portal';
	import NewsCard from './NewsCard.svelte';

	export let fallbackDate: string | null = null;

	type Target = { date: string; category: Category; id: string; href: string };

	const VALID_CATEGORIES: Category[] = ['news', 'research', 'social', 'github_trending'];
	const OPEN_DELAY = 280;
	const CLOSE_DELAY = 180;
	const PANEL_WIDTH = 440;
	const PANEL_HEIGHT = 590;
	const MARGIN = 12;
	const GAP = 8;

	let target: Target | null = null;
	let item: NewsItem | null = null;
	let loading = false;
	let panel: HTMLDivElement | null = null;
	let placementAnchor: HTMLAnchorElement | null = null;
	let triggerAnchor: HTMLAnchorElement | null = null;
	let requestToken = 0;
	let openTimer: ReturnType<typeof setTimeout> | null = null;
	let closeTimer: ReturnType<typeof setTimeout> | null = null;
	let copiedTimer: ReturnType<typeof setTimeout> | null = null;
	let copied = false;
	let canHover = false;
	let isSheet = false;
	let top = 0;
	let left = 0;
	let width = PANEL_WIDTH;
	let maxHeight = PANEL_HEIGHT;
	let placeAbove = false;

	$: sourceUrl = item && isSafeUrl(item.url) ? item.url : null;
	$: sourceAction =
		target?.category === 'research'
			? 'Open research'
			: target?.category === 'social'
				? 'Open post'
				: target?.category === 'github_trending'
					? 'Open repository'
					: 'Read article';

	function parseTarget(anchor: HTMLAnchorElement): Target | null {
		let url: URL;
		try {
			url = new URL(anchor.href, window.location.href);
		} catch {
			return null;
		}
		if (url.origin !== window.location.origin) return null;

		const id = url.hash.match(/^#item-([A-Za-z0-9_-]+)$/)?.[1];
		const category = url.searchParams.get('category') as Category | null;
		const date = url.searchParams.get('date') ?? fallbackDate;
		if (!id || !date || !category || !VALID_CATEGORIES.includes(category)) return null;

		return {
			date,
			category,
			id,
			href: `${url.pathname}${url.search}${url.hash}`
		};
	}

	function internalLinkFrom(node: EventTarget | null): HTMLAnchorElement | null {
		return node instanceof Element
			? (node.closest('a.internal-link') as HTMLAnchorElement | null)
			: null;
	}

	function cancelOpen() {
		if (openTimer) clearTimeout(openTimer);
		openTimer = null;
	}

	function cancelClose() {
		if (closeTimer) clearTimeout(closeTimer);
		closeTimer = null;
	}

	function close({ restoreFocus = false } = {}) {
		cancelOpen();
		cancelClose();
		requestToken += 1;
		target = null;
		item = null;
		loading = false;
		placementAnchor = null;
		copied = false;
		if (copiedTimer) clearTimeout(copiedTimer);
		copiedTimer = null;
		if (restoreFocus) triggerAnchor?.focus({ preventScroll: true });
	}

	function place() {
		if (isSheet || !placementAnchor?.isConnected) return;
		const rect = placementAnchor.getBoundingClientRect();
		const viewportWidth = window.innerWidth;
		const viewportHeight = window.innerHeight;
		const below = viewportHeight - rect.bottom - GAP - MARGIN;
		const above = rect.top - GAP - MARGIN;

		placeAbove = below < 330 && above > below;
		maxHeight = Math.max(300, Math.min(PANEL_HEIGHT, placeAbove ? above : below));
		top = placeAbove ? rect.top - GAP - maxHeight : rect.bottom + GAP;
		top = Math.max(MARGIN, Math.min(top, viewportHeight - maxHeight - MARGIN));
		width = Math.min(PANEL_WIDTH, viewportWidth - MARGIN * 2);
		left = Math.max(MARGIN, Math.min(rect.left, viewportWidth - width - MARGIN));
	}

	async function open(
		anchor: HTMLAnchorElement,
		{ focus = false, navigateOnMiss = false }: { focus?: boolean; navigateOnMiss?: boolean } = {}
	) {
		const next = parseTarget(anchor);
		if (!next) return;

		cancelOpen();
		cancelClose();
		const token = ++requestToken;
		const nested = !!panel?.contains(anchor);
		if (!nested) {
			placementAnchor = anchor;
			triggerAnchor = anchor;
		}
		target = next;
		item = peekItem(next.date, next.id);
		loading = !item;

		await tick();
		if (token !== requestToken) return;
		if (!nested) place();
		if (focus) panel?.focus({ preventScroll: true });
		if (item) return;

		const resolved = await resolveItem(next.date, next.category, next.id);
		if (token !== requestToken) return;
		if (!resolved) {
			close();
			if (navigateOnMiss) void goto(next.href);
			return;
		}

		item = resolved;
		loading = false;
		await tick();
		if (token === requestToken && !nested) place();
	}

	function scheduleOpen(anchor: HTMLAnchorElement) {
		cancelOpen();
		openTimer = setTimeout(() => {
			openTimer = null;
			void open(anchor);
		}, OPEN_DELAY);
	}

	function scheduleClose() {
		cancelClose();
		closeTimer = setTimeout(() => {
			closeTimer = null;
			close();
		}, CLOSE_DELAY);
	}

	async function copyLink() {
		if (!target) return;
		try {
			await navigator.clipboard.writeText(new URL(target.href, window.location.href).toString());
			copied = true;
			if (copiedTimer) clearTimeout(copiedTimer);
			copiedTimer = setTimeout(() => (copied = false), 1800);
		} catch {
			copied = false;
		}
	}

	function onClick(event: MouseEvent) {
		const link = internalLinkFrom(event.target);
		if (link) {
			if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;
			if (!parseTarget(link)) return;
			event.preventDefault();
			void open(link, { focus: true, navigateOnMiss: true });
			return;
		}
		if (target && event.target instanceof Node && !panel?.contains(event.target)) close();
	}

	function onPointerOver(event: PointerEvent) {
		if (!canHover || event.pointerType === 'touch') return;
		const link = internalLinkFrom(event.target);
		if (link) {
			cancelClose();
			scheduleOpen(link);
		}
	}

	function onPointerOut(event: PointerEvent) {
		if (!canHover || event.pointerType === 'touch') return;
		const link = internalLinkFrom(event.target);
		if (!link) return;
		const next = event.relatedTarget;
		if (next instanceof Node && panel?.contains(next)) return;
		scheduleClose();
	}

	function onFocusIn(event: FocusEvent) {
		const link = internalLinkFrom(event.target);
		if (!link || panel?.contains(link)) return;
		cancelClose();
		scheduleOpen(link);
	}

	function onKeydown(event: KeyboardEvent) {
		if (event.key !== 'Escape' || !target) return;
		event.preventDefault();
		close({ restoreFocus: true });
	}

	onMount(() => {
		const hoverQuery = window.matchMedia('(any-hover: hover)');
		const sheetQuery = window.matchMedia('(max-width: 640px)');
		canHover = hoverQuery.matches;
		isSheet = sheetQuery.matches;

		const onHoverChange = (event: MediaQueryListEvent) => (canHover = event.matches);
		const onSheetChange = (event: MediaQueryListEvent) => {
			isSheet = event.matches;
			place();
		};
		const onViewportChange = () => place();

		hoverQuery.addEventListener('change', onHoverChange);
		sheetQuery.addEventListener('change', onSheetChange);
		document.addEventListener('click', onClick, true);
		document.addEventListener('pointerover', onPointerOver);
		document.addEventListener('pointerout', onPointerOut);
		document.addEventListener('focusin', onFocusIn);
		document.addEventListener('keydown', onKeydown);
		window.addEventListener('scroll', onViewportChange, true);
		window.addEventListener('resize', onViewportChange);

		return () => {
			close();
			hoverQuery.removeEventListener('change', onHoverChange);
			sheetQuery.removeEventListener('change', onSheetChange);
			document.removeEventListener('click', onClick, true);
			document.removeEventListener('pointerover', onPointerOver);
			document.removeEventListener('pointerout', onPointerOut);
			document.removeEventListener('focusin', onFocusIn);
			document.removeEventListener('keydown', onKeydown);
			window.removeEventListener('scroll', onViewportChange, true);
			window.removeEventListener('resize', onViewportChange);
		};
	});
</script>

<div class="preview-host" use:portal>
	{#if target}
		{#if isSheet}
			<button class="scrim" type="button" aria-label="Close source preview" on:click={() => close()}></button>
		{/if}

		<div
			class="preview-panel"
			class:sheet={isSheet}
			class:above={placeAbove}
			bind:this={panel}
			style={isSheet ? undefined : `top:${top}px;left:${left}px;width:${width}px;max-height:${maxHeight}px`}
			role="dialog"
			aria-modal={isSheet}
			aria-label={item ? `Source preview: ${item.title}` : 'Loading source preview'}
			tabindex="-1"
			on:pointerenter={cancelClose}
			on:pointerleave={scheduleClose}
		>
			<div class="preview-bar">
				<div>
					<p>Evidence preview</p>
					<span>{target.category.replace('_', ' ')}</span>
				</div>
				<button type="button" aria-label="Close source preview" on:click={() => close({ restoreFocus: true })}>
					&times;
				</button>
			</div>

			<div class="preview-body">
				{#if item}
					<NewsCard
						{item}
						category={target.category}
						date={target.date}
						showCategory
						anchor={false}
						showActions={false}
					/>
				{:else if loading}
					<div class="skeleton" aria-label="Loading source">
						<span></span><span></span><span></span><span></span>
					</div>
				{/if}
			</div>

			<div class="preview-actions">
				{#if sourceUrl}
					<a class="primary-action" href={sourceUrl} target="_blank" rel="noopener noreferrer">
						{sourceAction} <span aria-hidden="true">&nearr;</span>
					</a>
				{/if}
				<a class="secondary-action" href={target.href} on:click={() => close()}>Open card</a>
				<button class="secondary-action" type="button" on:click={copyLink}>
					{copied ? 'Copied' : 'Share'}
				</button>
			</div>
		</div>
	{/if}
</div>

<style>
	.preview-host {
		position: absolute;
		inset: 0 auto auto 0;
		width: 0;
		height: 0;
	}

	.scrim {
		position: fixed;
		inset: 0;
		z-index: 80;
		border: 0;
		background: rgb(3 6 16 / 0.72);
		backdrop-filter: blur(4px);
	}

	.preview-panel {
		position: fixed;
		z-index: 81;
		display: flex;
		flex-direction: column;
		overflow: hidden;
		border: 1px solid rgb(255 255 255 / 0.14);
		border-radius: 20px;
		background: rgba(15, 20, 34, 0.98);
		box-shadow: 0 28px 90px rgb(0 0 0 / 0.58), 0 0 0 1px rgb(99 102 241 / 0.08);
		outline: none;
	}

	.preview-panel.sheet {
		inset: auto 0 0 0;
		width: 100%;
		max-height: min(86vh, 720px);
		border-radius: 24px 24px 0 0;
	}

	.preview-bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		padding: 0.75rem 1rem;
		border-bottom: 1px solid rgb(255 255 255 / 0.08);
		background: linear-gradient(90deg, rgb(99 102 241 / 0.16), transparent);
	}

	.preview-bar p {
		margin: 0;
		color: #fff;
		font-size: 0.72rem;
		font-weight: 800;
		letter-spacing: 0.16em;
		text-transform: uppercase;
	}

	.preview-bar span {
		color: #aaa7bb;
		font-size: 0.72rem;
		text-transform: capitalize;
	}

	.preview-bar button {
		display: grid;
		width: 2rem;
		height: 2rem;
		place-items: center;
		border: 1px solid rgb(255 255 255 / 0.1);
		border-radius: 999px;
		background: rgb(255 255 255 / 0.05);
		color: #d8d6e2;
		font-size: 1.25rem;
		cursor: pointer;
	}

	.preview-body {
		min-height: 0;
		overflow-y: auto;
		overscroll-behavior: contain;
		scrollbar-width: thin;
	}

	.preview-body :global(.card) {
		border: 0;
		border-radius: 0;
		background: transparent;
		box-shadow: none;
		animation: none;
	}

	.preview-actions {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.75rem;
		border-top: 1px solid rgb(255 255 255 / 0.09);
		background: #111727;
	}

	.primary-action {
		flex: 1;
		padding: 0.65rem 0.8rem;
		border-radius: 11px;
		background: linear-gradient(135deg, #6366f1, #7c3aed);
		color: #fff;
		font-size: 0.84rem;
		font-weight: 800;
		text-align: center;
		white-space: nowrap;
	}

	.secondary-action {
		border: 0;
		background: transparent;
		color: #b9b6c8;
		font-size: 0.78rem;
		font-weight: 700;
		white-space: nowrap;
		cursor: pointer;
	}

	.primary-action:hover,
	.secondary-action:hover {
		color: #fff;
	}

	.skeleton {
		display: flex;
		flex-direction: column;
		gap: 0.7rem;
		padding: 2rem;
	}

	.skeleton span {
		height: 0.85rem;
		border-radius: 999px;
		background: rgb(255 255 255 / 0.08);
		animation: pulse 1.4s ease-in-out infinite alternate;
	}

	.skeleton span:nth-child(1) { width: 35%; }
	.skeleton span:nth-child(2) { width: 100%; }
	.skeleton span:nth-child(3) { width: 82%; }
	.skeleton span:nth-child(4) { width: 55%; }

	@keyframes pulse {
		to { opacity: 0.35; }
	}

	@media (max-width: 640px) {
		.preview-actions {
			padding-bottom: max(0.9rem, env(safe-area-inset-bottom));
		}

		.primary-action {
			min-width: 0;
		}
	}
</style>
