<script lang="ts">
	import logo from '$lib/assets/image/logo.png';
</script>

<svelte:head>
	<title>PurePy: a pure, functional subset of Python</title>
</svelte:head>

<section id="top" class="hero">
	<h1><img class="hero-logo" src={logo} alt="PurePy" /></h1>
	<p class="tagline">A pure, functional subset of Python for scientific computing</p>
	<p class="lede">
		A versioned standard with a formal grammar, formal semantics, and a reference checker for a
		side-effect-free subset of Python.
	</p>
	<div class="cta">
		<a class="button primary" href="https://github.com/pure-py/pure-py-spec/releases/latest"
			>Read the spec</a
		>
		<a class="button" href="https://github.com/pure-py/pure-py-spec">GitHub</a>
	</div>
</section>

<section id="overview" class="prose">
	<h2>Overview</h2>
	<p>
		PurePy defines a pure, side-effect-free subset of Python. It is aimed initially at researchers
		in programming languages and pedagogy, and is intended to grow into a common language for
		scientific computing, supporting portable applications in modelling, data processing, analysis,
		and visualisation.
	</p>
	<p>
		The standard defines a versioned formal grammar, a formal semantics, and a reference checker.
		Every compliant implementation accepts any valid PurePy program and behaves according to the
		formal semantics.
	</p>
</section>

<section class="code-sample">
	<pre><code><span class="tok-kw">from</span> dataclasses <span class="tok-kw">import</span> dataclass
<span class="tok-kw">from</span> typing <span class="tok-kw">import</span> <span class="tok-type">Any</span>

<span class="tok-decorator">@dataclass</span>
<span class="tok-kw">class</span> <span class="tok-class">Point</span>:
    x: <span class="tok-type">Any</span>
    y: <span class="tok-type">Any</span>

<span class="tok-kw">def</span> <span class="tok-fn">describe</span>(p):
    <span class="tok-kw">match</span> p:
        <span class="tok-kw">case</span> <span class="tok-class">Point</span>(<span class="tok-num">0</span>, <span class="tok-num">0</span>):
            <span class="tok-kw">return</span> <span class="tok-str">"origin"</span>
        <span class="tok-kw">case</span> <span class="tok-class">Point</span>(x, y):
            <span class="tok-kw">return</span> <span class="tok-str">"point"</span>

<span class="tok-builtin">print</span>(<span class="tok-fn">describe</span>(<span class="tok-class">Point</span>(<span class="tok-num">3</span>, <span class="tok-num">4</span>)))</code></pre>
</section>

<section id="features" class="features">
	<h2>Why PurePy</h2>
	<div class="grid">
		<div class="card">
			<h3>Pure &amp; functional</h3>
			<p>No side effects. Functions are referentially transparent.</p>
		</div>
		<div class="card">
			<h3>Pythonic</h3>
			<p>
				A strict subset of Python: every valid PurePy program is valid Python, and runs with
				exactly the same runtime behaviour.
			</p>
		</div>
		<div class="card">
			<h3>Formally specified</h3>
			<p>A grammar, well-formedness rules, and an operational semantics.</p>
		</div>
		<div class="card">
			<h3>Portable</h3>
			<p>
				Python dialects are compliant by definition, checked on CPython, PyPy, GraalPy and Pyodide.
				Research languages like <a href="https://f.luid.org">Fluid</a> and
				<a href="https://github.com/plas4sci/fortl">Fortl</a> can be too.
			</p>
		</div>
		<div class="card">
			<h3>For science</h3>
			<p>Reproducible, deterministic, and easy to reason about.</p>
		</div>
		<div class="card">
			<h3>Checkable</h3>
			<p>A reference checker decides membership of the subset and flags use of unassigned variables.</p>
		</div>
	</div>
</section>
