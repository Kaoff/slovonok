<script lang="ts">
	import { api } from '../api';
	import { onDestroy } from 'svelte';
	import { t } from '../i18n.svelte';
	import type { Mode, Word, WordDisplayMode } from '../types';
	import Segmented from '../ui/Segmented.svelte';
	import Toggle from '../ui/Toggle.svelte';
	import LearnWizard from './LearnWizard.svelte';
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
	// --- "Sounds like": variants and tolerance ---
	let learning = $state(false);
	const tolerances = $derived<{ value: string; label: string }[]>([
		{ value: '0', label: t('word.tolerance.0') },
		{ value: '1', label: t('word.tolerance.1') },
		{ value: '2', label: t('word.tolerance.2') }
	]);

	// Short words can't take the full tolerance (same rule as the server: 4 sounds must match).
	// The server knows the sounds, so ask it, a moment after typing stops.
	const MIN_MATCHED_SOUNDS = 4;
	let soundCount = $state<number | null>(null);
	let askTimer: ReturnType<typeof setTimeout> | undefined;
	$effect(() => {
		const text = word.word;
		if (word.mode !== 'phonetic' || word.tolerance === 0 || !text.trim()) {
			soundCount = null;
			return;
		}
		clearTimeout(askTimer);
		askTimer = setTimeout(async () => {
			try {
				const { sounds } = await api.phonemize([text]);
				// A grapheme = a sound with its diacritics (nasal vowels)
				const segmenter = new Intl.Segmenter(undefined, { granularity: 'grapheme' });
				soundCount = [...segmenter.segment(sounds[0].replace(/\s+/g, ''))].length;
			} catch {
				soundCount = null;
			}
		}, 400);
	});
	onDestroy(() => clearTimeout(askTimer));
	const effectiveTolerance = $derived(
		soundCount === null
			? null
			: Math.max(0, Math.min(word.tolerance, soundCount - MIN_MATCHED_SOUNDS))
	);

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

	<section class="space-y-3">
		<div class="flex flex-wrap items-center gap-3">
			<h3 class="label text-base">{t('word.variants')}</h3>
			<button class="key text-xs" onclick={() => (learning = true)} disabled={!word.word.trim()}>
				{t('word.learn')}
			</button>
			<button class="key text-xs" onclick={() => word.variants.push('')}>
				+ {t('word.variantAdd')}
			</button>
		</div>
		<p class="text-xs text-muted">{t('word.variantsHint')}</p>
		{#if word.variants.length}
			<ul class="space-y-1.5">
				{#each word.variants as variant, i (i)}
					<li class="flex items-center gap-2">
						<input
							class="input flex-1"
							placeholder={t('word.variantPlaceholder')}
							aria-label={t('word.variants')}
							value={variant}
							oninput={(e) => (word.variants[i] = e.currentTarget.value)}
						/>
						<button
							class="key-danger"
							title={t('word.remove')}
							aria-label={t('word.remove')}
							onclick={() => word.variants.splice(i, 1)}>✕</button
						>
					</li>
				{/each}
			</ul>
		{/if}

		{#if word.mode === 'phonetic'}
			<div class="flex flex-wrap items-center gap-3">
				<span class="label">{t('word.tolerance')}</span>
				<Segmented
					bind:value={() => String(word.tolerance), (value) => (word.tolerance = Number(value))}
					options={tolerances}
				/>
			</div>
			<p class="text-xs text-muted">{t('word.toleranceHint')}</p>
			{#if effectiveTolerance !== null && effectiveTolerance < word.tolerance}
				<p class="text-xs text-accent">{t('word.toleranceShort', { count: effectiveTolerance })}</p>
			{/if}
		{/if}
		{#if word.variants.length || word.tolerance > 0}
			<p class="text-xs text-accent">{t('word.falsePositives')}</p>
		{/if}
	</section>

	<PunishmentPicker bind:selection={word.punishments} />
	<LearnWizard bind:open={learning} bind:word />
</article>
