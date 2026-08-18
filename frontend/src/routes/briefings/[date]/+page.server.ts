import { error } from '@sveltejs/kit';
import { adjacentDates, briefingEntries, loadBriefing } from '$lib/server/briefingData';

export const prerender = true;
export const entries = briefingEntries;

export function load({ params }) {
	const summary = loadBriefing(params.date);
	if (!summary) error(404, 'Briefing not found');
	return { summary, ...adjacentDates(params.date) };
}
