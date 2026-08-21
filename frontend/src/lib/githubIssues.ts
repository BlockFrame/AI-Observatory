const NEW_ISSUE_URL = 'https://github.com/BlockFrame/wiredframe-radar/issues/new';

export type GitHubIssueDraft = {
	title: string;
	body: string;
	labels?: string[];
};

export function buildGitHubIssueUrl({ title, body, labels = [] }: GitHubIssueDraft): string {
	const params = new URLSearchParams({ title, body });
	if (labels.length > 0) params.set('labels', labels.join(','));
	return `${NEW_ISSUE_URL}?${params.toString()}`;
}

export function openGitHubIssue(draft: GitHubIssueDraft): void {
	window.open(buildGitHubIssueUrl(draft), '_blank', 'noopener,noreferrer');
}
