<svelte:head>
	<title>PurePy — a pure, functional subset of Python</title>
</svelte:head>

<section id="top" class="hero">
	<h1>Pure<span class="brand-accent">Py</span></h1>
	<p class="tagline">A pure, functional subset of Python — for science.</p>
	<p class="lede">
		A versioned standard — grammar, formal semantics, and a reference checker — for a
		side-effect-free Python you can reason about, and run on any PurePy-compliant implementation.
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
		PurePy defines a pure, side-effect-free subset of Python, aimed initially at researchers in
		programming languages and pedagogy, and intended to grow into a common language for scientific
		computing — efficient, portable applications in modelling, data processing, analysis and
		visualisation.
	</p>
	<p>
		The standard defines a (versioned) formal grammar, a formal semantics, and a reference checker.
		Every PurePy-compliant language must accept any valid PurePy program and behave in accordance
		with the formal semantics — so the same program runs the same way everywhere.
	</p>
</section>

<section class="code-sample">
	<pre><code>from dataclasses import dataclass
from typing import Any

@dataclass
class Point:
    x: Any
    y: Any

def describe(p):
    match p:
        case Point(0, 0):
            return "origin"
        case Point(x, y):
            return "point"

print(describe(Point(3, 4)))</code></pre>
</section>

<section id="features" class="features">
	<h2>Why PurePy</h2>
	<div class="grid">
		<div class="card">
			<h3>Pure &amp; functional</h3>
			<p>No side effects: functions are referentially transparent and easy to reason about.</p>
		</div>
		<div class="card">
			<h3>Pythonic</h3>
			<p>A strict subset — every valid PurePy program is valid Python.</p>
		</div>
		<div class="card">
			<h3>Formally specified</h3>
			<p>A grammar, well-formedness rules, and an operational semantics.</p>
		</div>
		<div class="card">
			<h3>Portable</h3>
			<p>One standard, many compliant implementations — CPython, JAX, Fluid, and more.</p>
		</div>
		<div class="card">
			<h3>For science</h3>
			<p>Designed for modelling, data processing, analysis and visualisation.</p>
		</div>
		<div class="card">
			<h3>Checkable</h3>
			<p>An executable reference checker decides membership of the subset.</p>
		</div>
	</div>
</section>
