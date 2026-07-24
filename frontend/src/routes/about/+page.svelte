<svelte:head>
	<title>About | AI Observatory</title>
</svelte:head>

<div class="max-w-4xl mx-auto px-6 lg:px-10 py-8">
	<h1 class="text-2xl font-bold text-trend-gray-800 dark:text-trend-gray-100 mb-8">
		About AI News Daily
	</h1>

	<!-- About This Project -->
	<section class="card mb-8">
		<h2 class="text-lg font-semibold text-trend-gray-800 dark:text-trend-gray-100 mb-4">
			About This Project
		</h2>
		<div class="prose dark:prose-invert max-w-none text-trend-gray-600 dark:text-trend-gray-400">
			<p>
				<strong>AI Observatory</strong> is a solution of the <a href="https://www.wiredframe.xyz/" target="_blank" rel="noopener noreferrer" class="text-primary hover:underline font-semibold">Wiredframe Project</a> that delivers strategic daily briefings on AI/ML developments,
				helping you stay current with the fast-moving world of artificial intelligence.
			</p>
			<p>
				This project is a custom fork of the excellent AI News Aggregator created by the <a href="https://www.trendmicro.com/" target="_blank" rel="noopener noreferrer" class="text-primary hover:underline font-semibold">TrendAI AATF</a>. 
				While we maintain the robust underlying multi-agent logic of the original architecture, this instance introduces deep customizations: 
				we have tailored the data sources, integrated continuous analysis of <strong>GitHub Repositories</strong>, 
				and entirely redesigned the information representation to focus on strategic insights, business implications, and trend velocity.
			</p>
			<p>
				The aggregator uses a multi-agent pipeline powered by native AI models with adaptive thinking
				to gather, analyze, and synthesize content from diverse sources into coherent daily reports.
			</p>
			<p>
				Originally developed as an internal tool, it is now open-sourced so others can run their own instances or contribute improvements. You can explore the source code on <a href="https://github.com/BlockFrame/AI-Observatory" target="_blank" rel="noopener noreferrer" class="text-primary hover:underline font-semibold">our GitHub Repository</a>.
			</p>
		</div>
	</section>

	<!-- How It Works -->
	<section class="card mb-8">
		<h2 class="text-lg font-semibold text-trend-gray-800 dark:text-trend-gray-100 mb-4">
			How It Works
		</h2>
		<div class="prose dark:prose-invert max-w-none text-trend-gray-600 dark:text-trend-gray-400">
			<div class="my-8 p-6 bg-surface-variant/30 rounded-2xl border border-white/5 overflow-x-auto">
				<div class="flex items-center min-w-[600px] justify-between gap-2 text-sm">
					<!-- Data Sources -->
					<div class="flex flex-col gap-2 w-32">
						<div class="px-3 py-2 bg-background rounded-lg border border-white/10 text-center font-medium text-trend-gray-300">News & RSS</div>
						<div class="px-3 py-2 bg-background rounded-lg border border-white/10 text-center font-medium text-trend-gray-300">Research</div>
						<div class="px-3 py-2 bg-background rounded-lg border border-white/10 text-center font-medium text-trend-gray-300">Social</div>
						<div class="px-3 py-2 bg-background rounded-lg border border-white/10 text-center font-medium text-trend-gray-300">GitHub</div>
					</div>
					
					<!-- Arrow -->
					<div class="text-primary/50 text-xl font-bold">➔</div>

					<!-- Gatherers -->
					<div class="flex flex-col items-center gap-1">
						<div class="w-32 px-3 py-4 bg-surface rounded-xl border border-primary/20 text-center shadow-lg shadow-primary/5">
							<div class="font-bold text-primary mb-1">Gatherers</div>
							<div class="text-xs text-on-surface-variant">Parallel Collection</div>
						</div>
					</div>

					<!-- Arrow -->
					<div class="text-primary/50 text-xl font-bold">➔</div>

					<!-- Analyzers -->
					<div class="flex flex-col items-center gap-1">
						<div class="w-32 px-3 py-4 bg-surface rounded-xl border border-primary/20 text-center shadow-lg shadow-primary/5">
							<div class="font-bold text-primary mb-1">Analyzers</div>
							<div class="text-xs text-on-surface-variant">Adaptive Thinking</div>
						</div>
					</div>

					<!-- Arrow -->
					<div class="text-primary/50 text-xl font-bold">➔</div>

					<!-- Orchestrator -->
					<div class="flex flex-col items-center gap-1">
						<div class="w-36 px-3 py-4 bg-primary/10 rounded-xl border border-primary/40 text-center shadow-[0_0_20px_rgba(var(--color-primary),0.15)] relative overflow-hidden">
							<div class="absolute -inset-4 bg-primary/20 rounded-full blur-xl animate-pulse"></div>
							<div class="relative z-10 font-bold text-primary mb-1">Orchestrator</div>
							<div class="relative z-10 text-xs text-on-surface-variant">Cross-topic Synth</div>
						</div>
					</div>

					<!-- Arrow -->
					<div class="text-primary/50 text-xl font-bold">➔</div>

					<!-- Output -->
					<div class="flex flex-col gap-2 w-32">
						<div class="px-3 py-2 bg-background rounded-lg border border-white/10 text-center font-medium text-trend-gray-300">Daily Briefing</div>
						<div class="px-3 py-2 bg-background rounded-lg border border-white/10 text-center font-medium text-trend-gray-300">MCP Server</div>
					</div>
				</div>
				<div class="text-center text-xs text-on-surface-variant mt-6">AI Observatory Pipeline Architecture</div>
			</div>
			<p>Each day, the pipeline runs through several phases:</p>
			<ol>
				<li>
					<strong>Parallel Gathering</strong> - Four specialized gatherers collect content from
					different source types: News (RSS feeds and linked articles), Research (arXiv papers
					and research blogs), Social (Twitter, Bluesky, Mastodon), and GitHub Trending.
				</li>
				<li>
					<strong>Category Analysis</strong> - Four analyzers process each category using
					adaptive thinking profiles to identify key developments, assess importance, and generate summaries.
				</li>
				<li>
					<strong>Cross-Category Topic Detection</strong> - The system identifies themes that
					span multiple categories, revealing broader narratives in the day's news.
				</li>
				<li>
					<strong>Executive Summary Generation</strong> - A high-level summary is created that
					captures the most important developments across all categories.
				</li>
				<li>
					<strong>Link Enrichment</strong> - Internal links are added to summaries so you can
					easily navigate to referenced items.
				</li>
			</ol>
		</div>
	</section>

	<!-- AI-Generated Content Disclaimer -->
	<section class="card mb-8 border-2 border-amber-500 dark:border-amber-600">
		<div class="flex items-start gap-3">
			<div class="shrink-0 mt-1">
				<svg class="w-6 h-6 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
					<path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
				</svg>
			</div>
			<div>
				<h2 class="text-lg font-semibold text-trend-gray-800 dark:text-trend-gray-100 mb-4">
					AI-Generated Content Disclaimer
				</h2>
				<div class="prose dark:prose-invert max-w-none text-trend-gray-600 dark:text-trend-gray-400">
					<p>
						<strong>All summaries and analysis on this site are AI-generated</strong>. 
						The content is produced entirely by automated processes without human editorial review, 
						leveraging state-of-the-art models for data synthesis.
					</p>
					<p>
						The pipeline uses <strong>adaptive thinking</strong> for complex analysis tasks like 
						cross-category topic detection, business implication extraction, and executive summaries.
					</p>
					<p>
						<strong>While we strive for accuracy, AI can and does make errors.</strong> These may include:
					</p>
					<ul>
						<li>Misattributing quotes or claims to the wrong source</li>
						<li>Misinterpreting technical details in research papers</li>
						<li>Missing important context or nuance</li>
						<li>Hallucinating details that weren't in the original sources</li>
					</ul>
					<p>
						<strong>Source links are provided throughout</strong> so you can verify information
						by reading the original content. We strongly recommend checking primary sources for
						any information you plan to act on or share.
					</p>
					<p class="font-medium">
						Always verify important information from primary sources.
					</p>
				</div>
			</div>
		</div>
	</section>

	<!-- Open Source -->
	<section class="card">
		<h2 class="text-lg font-semibold text-trend-gray-800 dark:text-trend-gray-100 mb-4">
			Open Source
		</h2>
		<div class="prose dark:prose-invert max-w-none text-trend-gray-600 dark:text-trend-gray-400">
			<p>
				This project is open source under the <strong>Apache 2.0 License</strong>, which allows
				you to use, modify, and distribute the code freely.
			</p>
			<p>
				The source code is available on GitHub:
			</p>
			<p>
				<a
					href="https://github.com/BlockFrame/AI-Observatory"
					target="_blank"
					rel="noopener noreferrer"
					class="inline-flex items-center gap-2 text-primary hover:underline font-semibold"
				>
					<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
						<path fill-rule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" clip-rule="evenodd" />
					</svg>
					BlockFrame/AI-Observatory
				</a>
			</p>
			<p>
				Contributions are welcome! Whether you want to add new data sources, improve the analysis
				prompts, enhance the frontend, or fix bugs, we'd love to see your pull requests.
			</p>
		</div>
	</section>
</div>
