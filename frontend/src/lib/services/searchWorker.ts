/**
 * Search worker: builds and queries a MiniSearch index off the main thread.
 *
 * The pipeline ships a single compact corpus (web/data/search-corpus.json).
 * This worker fetches it once, builds the index, and answers search queries.
 */

import MiniSearch from 'minisearch';
import type { SearchDocument, Category } from '$lib/types';

interface CorpusDoc extends SearchDocument {
	ref: string;
}

interface IndexedCorpusDoc extends CorpusDoc {
	itemId: string;
}

type InitMessage = { type: 'init' };
type SearchMessage = {
	type: 'search';
	id: number;
	query: string;
	category?: Category;
	limit: number;
};
type IncomingMessage = InitMessage | SearchMessage;

let miniSearch: MiniSearch<IndexedCorpusDoc> | null = null;

function buildIndex(docs: CorpusDoc[]): MiniSearch<IndexedCorpusDoc> {
	const index = new MiniSearch<IndexedCorpusDoc>({
		idField: 'ref',
		fields: ['title', 'summary', 'source'],
		storeFields: ['itemId', 'title', 'summary', 'source', 'category', 'date', 'url', 'importance'],
		searchOptions: {
			boost: { title: 10, summary: 5, source: 2 },
			prefix: true,
			fuzzy: 0.2
		}
	});
	// MiniSearch exposes its own index id as `result.id`. Preserve the actual
	// report item id separately so a search result can target the card anchor.
	index.addAll(docs.map((doc) => ({ ...doc, itemId: doc.id })));
	return index;
}

async function init(): Promise<void> {
	const response = await fetch('/data/search-corpus.json');
	if (!response.ok) {
		throw new Error(`Failed to fetch corpus: ${response.status}`);
	}
	const docs: CorpusDoc[] = await response.json();
	miniSearch = buildIndex(docs);
	postMessage({ type: 'ready', count: docs.length });
}

function runSearch(msg: SearchMessage): void {
	if (!miniSearch) {
		postMessage({ type: 'results', id: msg.id, results: [] });
		return;
	}

	const raw = miniSearch.search(msg.query, {
		filter: (result) => !msg.category || result.category === msg.category
	});

	raw.sort((a, b) => {
		const scoreDiff = b.score - a.score;
		if (Math.abs(scoreDiff) > 0.1) return scoreDiff;
		return (b.importance ?? 0) - (a.importance ?? 0);
	});

	const results = raw.slice(0, msg.limit).map((r) => ({
		ref: r.id as string,
		score: r.score,
		doc: {
			id: r.itemId as string,
			title: r.title,
			summary: r.summary,
			url: r.url,
			date: r.date,
			category: r.category,
			source: r.source,
			importance: r.importance
		} as SearchDocument
	}));

	postMessage({ type: 'results', id: msg.id, results });
}

self.onmessage = (event: MessageEvent<IncomingMessage>) => {
	const msg = event.data;
	if (msg.type === 'init') {
		init().catch((e) => {
			postMessage({ type: 'error', message: String(e) });
		});
	} else if (msg.type === 'search') {
		runSearch(msg);
	}
};
