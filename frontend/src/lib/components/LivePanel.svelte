<script lang="ts">
	import { tick } from 'svelte';
	import { app } from '../app.svelte';
	import { api } from '../api';
	import { i18n, t } from '../i18n.svelte';

	let text = $state('');
	let triggered = $state<string[] | null>(null);
	let screen: HTMLElement | undefined = $state();

	// Keep the display scrolled to the latest line.
	$effect(() => {
		void app.transcript.length;
		void app.transcript.at(-1)?.text;
		tick().then(() => screen?.scrollTo({ top: screen.scrollHeight }));
	});

	async function simulate(e: SubmitEvent) {
		e.preventDefault();
		if (!text.trim()) return;
		await app.flush();
		triggered = (await api.simulate(text)).triggered;
		text = '';
	}

	const time = (d: Date) =>
		d.toLocaleTimeString(i18n.locale, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
</script>

<!-- Transcript: takes the remaining height, its size never depends on the detections -->
<section class="flex min-h-0 flex-1 flex-col gap-3 panel p-5">
	<div class="space-y-1 text-sm">
		{#if !app.connected}
			<p class="flex items-center gap-2"><span class="led-red"></span>{t('live.disconnected')}</p>
		{:else if app.status?.listening}
			<p class="flex items-center gap-2"><span class="led-green"></span>{t('live.listening')}</p>
			<p class="truncate pl-4 text-xs text-muted">{app.status.microphone}</p>
		{:else}
			<p class="flex items-center gap-2"><span class="led"></span>{t('live.notListening')}</p>
		{/if}
		{#if app.status?.listener_error}
			<p class="text-xs text-danger">{app.status.listener_error}</p>
		{/if}
		{#if app.status?.phonetics_error}
			<p class="text-xs text-danger">{t('live.phoneticsError')}</p>
		{/if}
	</div>

	<h2 class="label">{t('live.transcript')}</h2>
	<ol bind:this={screen} class="min-h-0 flex-1 space-y-1 overflow-y-auto p-3 text-sm well">
		{#each app.transcript as line (line.id)}
			<li class={line.final ? '' : 'opacity-60'}>{line.text}</li>
		{:else}
			<li class="opacity-50">{t('live.waiting')}</li>
		{/each}
	</ol>

	<form class="space-y-1" onsubmit={simulate}>
		<div class="flex gap-2">
			<input
				class="input min-w-0 flex-1"
				placeholder={t('live.simulate')}
				aria-label={t('live.simulate')}
				bind:value={text}
			/>
			<button class="key">{t('live.send')}</button>
		</div>
		<!-- Reserved line: the result appearing doesn't push anything -->
		<p class="h-4 text-xs text-muted">
			{#if triggered}
				{triggered.length
					? t('live.triggered', { words: triggered.join(', ') })
					: t('live.nothing')}
			{/if}
		</p>
	</form>
</section>

<!-- Detections: fixed height, scrolls inside -->
<section class="flex h-60 shrink-0 flex-col gap-3 panel p-5" aria-live="polite">
	<h2 class="label">{t('live.detections')}</h2>
	<ul class="min-h-0 flex-1 space-y-1 overflow-y-auto text-sm">
		{#each app.detections as detection (detection.id)}
			<li class="flex items-center justify-between gap-2">
				<span class="flex min-w-0 items-center gap-2">
					<span class="led-red"></span>
					<span class="truncate">{detection.word}</span>
					<span class="text-xs text-accent">×{detection.count}</span>
				</span>
				<span class="text-xs text-muted tabular-nums">{time(detection.at)}</span>
			</li>
		{:else}
			<li class="text-muted">{t('live.noDetections')}</li>
		{/each}
	</ul>
</section>
