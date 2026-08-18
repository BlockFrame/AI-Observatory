/** In-memory item lookup used by internal-link previews. */
import type { Category, NewsItem } from '$lib/types';
import { loadCategoryData } from './dataLoader';

const items = new Map<string, NewsItem>();
const keyFor = (date: string, id: string) => `${date}:${id}`;

export function registerItems(date: string, list: NewsItem[] | undefined | null): void {
	if (!list) return;
	for (const item of list) {
		if (item?.id) items.set(keyFor(date, item.id), item);
	}
}

export function peekItem(date: string, id: string): NewsItem | null {
	return items.get(keyFor(date, id)) ?? null;
}

export async function resolveItem(
	date: string,
	category: Category,
	id: string
): Promise<NewsItem | null> {
	const cached = peekItem(date, id);
	if (cached) return cached;

	try {
		const data = await loadCategoryData(date, category);
		registerItems(date, data.items);
	} catch {
		return null;
	}

	return peekItem(date, id);
}
