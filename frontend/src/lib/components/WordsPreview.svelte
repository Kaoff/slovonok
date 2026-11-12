<!--
	Preview of the OBS words list: the real overlay page in an iframe (?preview), fed with the
	panel's current config (unsaved edits included) instead of the app's WebSocket.
	Shown at the size of an OBS canvas, then scaled down to fit.
-->
<script lang="ts">
	import { app } from '../app.svelte';

	// OBS canvas size, in pixels: the overlay is laid out for it, not for the panel's rem.
	const CANVAS_WIDTH = 1920;
	const CANVAS_HEIGHT = 1080;

	let frame = $state<HTMLIFrameElement>();
	let width = $state(0);
	const scale = $derived(width / CANVAS_WIDTH);

	function send() {
		const config = app.config;
		if (!config) return;
		// Only what the overlay reads; snapshot = plain data, as postMessage needs
		const message = $state.snapshot({
			type: 'config',
			config: { words: config.words, display: { words: config.display.words } }
		});
		frame?.contentWindow?.postMessage(message, location.origin);
	}

	// Re-sent on every change (the snapshot reads the whole config) and when the iframe has loaded
	$effect(send);

	/** Plays an animation on the first word of the preview. */
	export function play(kind: 'enter' | 'hit' | 'exit', name: string) {
		frame?.contentWindow?.postMessage({ type: 'play', kind, name }, location.origin);
	}
</script>

<div
	bind:clientWidth={width}
	class="relative aspect-video w-full overflow-hidden recess"
	style="background: repeating-conic-gradient(#1b2229 0% 25%, #11161b 0% 50%) 0 0 / 1.5rem 1.5rem;"
>
	<iframe
		bind:this={frame}
		title="Preview"
		src="/overlay/words/?preview"
		onload={send}
		class="absolute top-0 left-0 origin-top-left border-0"
		style="width: {CANVAS_WIDTH}px; height: {CANVAS_HEIGHT}px; transform: scale({scale}); color-scheme: normal;"
	></iframe>
</div>
