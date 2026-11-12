<!--
	A CSS textarea with syntax coloring, without an editor library: the colored code is drawn in a
	<pre> right behind a textarea whose text is transparent (only its caret and selection show).
	Both must keep the exact same font, padding and line breaks: no wrapping (wrap="off"), so a
	scrollbar on the textarea can't make lines break differently in the <pre>.
-->
<script lang="ts">
	import { highlight } from '../cssHighlight';

	let { value = $bindable(), label }: { value: string; label: string } = $props();

	let pre = $state<HTMLPreElement>();
	// A trailing newline in a textarea opens a line: the <pre> needs a character to show it too
	const html = $derived(highlight(value) + '\n');

	function syncScroll(e: Event) {
		const textarea = e.currentTarget as HTMLTextAreaElement;
		if (!pre) return;
		pre.scrollTop = textarea.scrollTop;
		pre.scrollLeft = textarea.scrollLeft;
	}

	/** Tab inserts two spaces instead of leaving the field (Shift+Tab still leaves it). */
	function onkeydown(e: KeyboardEvent) {
		if (e.key !== 'Tab' || e.shiftKey) return;
		e.preventDefault();
		const textarea = e.currentTarget as HTMLTextAreaElement;
		const { selectionStart: start, selectionEnd: end } = textarea;
		textarea.setRangeText('  ', start, end, 'end');
		value = textarea.value;
	}
</script>

<div class="editor relative min-h-64 flex-1 recess focus-within:border-accent">
	<!-- eslint-disable-next-line svelte/no-at-html-tags -- highlight() escapes every token -->
	<pre bind:this={pre} aria-hidden="true" class="code pointer-events-none">{@html html}</pre>
	<textarea
		class="code absolute inset-0 resize-none bg-transparent outline-none"
		spellcheck="false"
		autocomplete="off"
		wrap="off"
		aria-label={label}
		bind:value
		onscroll={syncScroll}
		{onkeydown}></textarea>
</div>

<style>
	.code {
		box-sizing: border-box;
		width: 100%;
		height: 100%;
		margin: 0;
		padding: 0.5rem 0.875rem;
		overflow: auto;
		font-family: var(--font-sans);
		font-size: 0.875rem;
		line-height: 1.5;
		tab-size: 2;
		white-space: pre;
		border: 0;
	}
	pre.code {
		overflow: hidden; /* follows the textarea's scroll */
		color: var(--color-fg);
	}
	textarea.code {
		color: transparent;
		-webkit-text-fill-color: transparent;
		caret-color: var(--color-accent);
	}
	textarea.code::selection {
		background: rgb(0 240 255 / 0.3);
	}

	/* Colors: the theme's cyan / magenta / lime, plus an amber for strings */
	.editor :global {
		.tok-comment {
			color: var(--color-muted);
			font-style: italic;
		}
		.tok-selector,
		.tok-function {
			color: var(--color-accent);
		}
		.tok-class,
		.tok-pseudo,
		.tok-attr,
		.tok-at,
		.tok-important {
			color: var(--color-danger);
		}
		.tok-property {
			color: var(--color-fg);
		}
		.tok-variable {
			color: #c9a7ff;
		}
		.tok-number,
		.tok-color {
			color: var(--color-ok);
		}
		.tok-string {
			color: #ffb86b;
		}
		.tok-keyword {
			color: #7fe9f2;
		}
		.tok-punct {
			color: var(--color-muted);
		}
	}
</style>
