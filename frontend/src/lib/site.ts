export const SITE = {
	name: 'Wiredframe Radar',
	visualName: 'R[AI]DAR',
	url: 'https://radar.wiredframe.xyz',
	description:
		'Evidence-linked daily intelligence on AI news, research, social signals, and open-source projects.',
	tagline: 'AI intelligence without the noise. Every signal linked to evidence.',
	githubUrl: 'https://github.com/BlockFrame/wiredframe-radar',
	parentName: 'Wiredframe',
	parentUrl: 'https://www.wiredframe.xyz',
	imagePath: '/logo.png'
} as const;

export function absoluteUrl(path = ''): string {
	if (!path || path === '/') return SITE.url;
	return `${SITE.url}${path.startsWith('/') ? path : `/${path}`}`;
}

