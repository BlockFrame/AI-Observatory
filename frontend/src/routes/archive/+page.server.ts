import { readDataIndex } from '$lib/server/briefingData';

export const prerender = true;

export function load() {
	return { index: readDataIndex() };
}
