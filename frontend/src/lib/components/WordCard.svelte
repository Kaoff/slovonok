<script lang="ts">
	import { api } from '../api';
	import { t } from '../i18n.svelte';
	import type { Mode, Word, WordDisplayMode } from '../types';
	import Segmented from '../ui/Segmented.svelte';
	import Toggle from '../ui/Toggle.svelte';
	import PunishmentPicker from './PunishmentPicker.svelte';

	let { word = $bindable(), onremove }: { word: Word; onremove: () => void } = $props();

	const modes = $derived<{ value: Mode; label: string }[]>([
		{ value: 'phonetic', label: t('word.phonetic') },
		{ value: 'exact', label: t('word.exact') }
	]);
	const displayModes = $derived<{ value: WordDisplayMode; label: string }[]>([
		{ value: 'shown', label: t('word.display.shown') },
		{ value: 'partial', label: t('word.display.partial') },
		{ value: 'hidden', label: t('word.display.hidden') }
	]);
	// Words added by a punishment can expire: show the time left
	let now = $state(Date.now());
	$effect(() => {
		if (word.expires_at === null) return;
		const timer = setInterval(() => (now = Date.now()), 1000);
		return () => clearInterval(timer);
	});
	const remaining = $derived(
		word.expires_at === null ? null : Math.max(0, Math.ceil(word.expires_at - now / 1000))
	);
	const clock = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

	function confirmRemove() {
		if (!word.word || confirm(t('word.confirmDelete', { word: word.word }))) onremove();
	}
</script>

<!-- A disabled word is shown entirely in grey: frame, buttons, counter, selected options -->
<article class="space-y-4 panel pt-6 transition-[filter] {word.enabled ? '' : 'grayscale'}">
	<header class="flex flex-wrap items-center gap-3">
		<Toggle bind:checked={word.enabled} title={t('word.enabled')} />
		<input
			class="input min-w-48 flex-1 text-lg font-strong tracking-wide {word.enabled
				? ''
				: 'text-muted'}"
			placeholder={t('word.placeholder')}
			bind:value={word.word}
		/>
		<div class="flex items-center gap-2" title={t('word.count')}>
			<span class="min-w-12 px-2 py-1 text-center text-lg well tabular-nums">{word.count}</span>
			<button
				class="key text-xs"
				disabled={word.count === 0}
				onclick={() => api.resetCount(word.id)}>{t('word.reset')}</button
			>
		</div>
		<button
			class="key-danger"
			title={t('word.delete')}
			aria-label={t('word.delete')}
			onclick={confirmRemove}>✕</button
		>
	</header>

	{#if word.auto}
		<p class="text-xs text-accent">
			＋ {t('word.auto')}{remaining === null
				? ''
				: ` · ${t('word.expiresIn', { time: clock(remaining) })}`}
		</p>
	{/if}

	<div class="space-y-3 module">
		<Segmented bind:value={word.mode} options={modes} />
		<div class="flex flex-wrap gap-x-8 gap-y-3">
			{#if word.mode === 'phonetic'}
				<Toggle
					bind:checked={word.word_end}
					label={t('word.wordEnd')}
					hint={t('word.wordEndHint')}
				/>
				<Toggle
					bind:checked={word.word_start}
					label={t('word.wordStart')}
					hint={t('word.wordStartHint')}
				/>
			{:else}
				<Toggle bind:checked={word.plural} label={t('word.plural')} hint={t('word.pluralHint')} />
			{/if}
		</div>
	</div>

	<section class="space-y-2">
		<div class="flex flex-wrap items-center gap-3">
			<h3 class="label text-base">{t('word.display')}</h3>
			<Segmented bind:value={word.display_mode} options={displayModes} />
		</div>
		<p class="text-xs text-muted">{t('word.displayHint')}</p>
	</section>

	<PunishmentPicker bind:selection={word.punishments} />
</article>
