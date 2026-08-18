import { error } from '@sveltejs/kit';
import type { Category } from '$lib/types';
import {
	adjacentDates,
	categoryEntries,
	loadBriefing,
	loadBriefingCategory
} from '$lib/server/briefingData';

export const prerender = true;
export const entries = categoryEntries;

export function load({ params }) {
	const category = params.category as Category;
	const summary = loadBriefing(params.date);
	const categoryData = loadBriefingCategory(params.date, category);
	if (!summary || !categoryData) error(404, 'Category briefing not found');
	return { summary, categoryData, category, ...adjacentDates(params.date) };
}
