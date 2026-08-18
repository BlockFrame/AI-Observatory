import { loadBriefing, readDataIndex } from '$lib/server/briefingData';

export const prerender = true;

export function load() {
	const index = readDataIndex();
	const summary = index.latestDate ? loadBriefing(index.latestDate) : null;
	return {
		summary,
		latestDate: index.latestDate,
		dates: index.dates.map((entry) => entry.date)
	};
}
