<script lang="ts">
	import '$lib/styles.css';
	import { headerLinks } from '$lib/config/nav';

	let { children } = $props();
</script>

<header class="site-header">
	<a class="brand" href="#top">Pure<span class="brand-accent">Py</span></a>
	<nav class="site-nav">
		{#each headerLinks as { url, title } (url)}
			<a href={url}>{title}</a>
		{/each}
	</nav>
</header>

<main>
	{@render children()}
</main>

<footer class="site-footer">
	<div class="footer-inner">
		<p>© PurePy contributors</p>
		<nav>
			<a href="https://github.com/pure-py/pure-py-spec">GitHub</a>
			<a href="https://github.com/pure-py/pure-py-spec/releases/latest">Specification (PDF)</a>
		</nav>
	</div>
</footer>
