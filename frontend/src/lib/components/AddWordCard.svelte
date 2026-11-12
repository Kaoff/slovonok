<!-- The "add a forbidden word" punishment: no media, a pool of words and a few options. -->
<script lang="ts">
	import { app } from '../app.svelte';
	import { api } from '../api';
	import { t } from '../i18n.svelte';
	import type { Mode, Punishment, PunishmentTest, WordDisplayMode } from '../types';
	import Segmented from '../ui/Segmented.svelte';
	import Slider from '../ui/Slider.svelte';
	import PunishmentPicker from './PunishmentPicker.svelte';

	let { punishment = $bindable(), onremove }: { punishment: Punishment; onremove: () => void } =
		$props();

	const options = $derived(punishment.add_word);

	// --- Pool: one word per line ---
	// The text is local so that typing a new line isn't trimmed away under the cursor;
	// it is re-read from the config only if the config changed from elsewhere.
	const parse = (text: string) =>
		text
			.split('\n')
			.map((line) => line.trim())
			.filter(Boolean);
	let poolText = $state(punishment.add_word.pool.join('\n'));
	$effect(() => {
		const pool = punishment.add_word.pool;
		if (parse(poolText).join('\n') !== pool.join('\n')) poolText = pool.join('\n');
	});

	const modes = $derived<{ value: Mode; label: string }[]>([
		{ value: 'phonetic', label: t('word.phonetic') },
		{ value: 'exact', label: t('word.exact') }
	]);
	const displayModes = $derived<{ value: WordDisplayMode; label: string }[]>([
		{ value: 'shown', label: t('word.display.shown') },
		{ value: 'partial', label: t('word.display.partial') },
		{ value: 'hidden', label: t('word.display.hidden') }
	]);
	const sources = $derived<{ value: 'trigger' | 'list'; label: string }[]>([
		{ value: 'trigger', label: t('addWord.fromTrigger') },
		{ value: 'list', label: t('addWord.fromList') }
	]);
	const lifetimes = $derived<{ value: 'forever' | 'timed'; label: string }[]>([
		{ value: 'forever', label: t('addWord.forever') },
		{ value: 'timed', label: t('addWord.timed') }
	]);

	const DEFAULT_LIFETIME = 60;
	const duration = (seconds: number) =>
		seconds >= 60 && seconds % 60 === 0 ? `${seconds / 60} min` : `${seconds} s`;

	// --- Test ---
	let testing = $state(false);
	let outcome = $state<PunishmentTest | null>(null);
	let error = $state<string | null>(null);

	async function test() {
		testing = true;
		error = null;
		outcome = null;
		try {
			await app.flush(); // the server must know the latest options
			outcome = await api.testPunishment(punishment.id);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			testing = false;
		}
	}
</script>

<article class="grid gap-5 panel pt-6 md:grid-cols-[11rem_1fr]">
	<div class="flex aspect-video items-center justify-center overflow-hidden p-1 recess">
		<span class="text-5xl text-danger" aria-hidden="true">＋</span>
	</div>

	<div class="space-y-4">
		<div class="flex flex-wrap items-center gap-2">
			<input
				class="input min-w-40 flex-1 text-lg font-strong tracking-wide"
				placeholder={t('punishment.name')}
				aria-label={t('punishment.name')}
				bind:value={punishment.name}
			/>
			<span class="label text-xs">{t('type.add_word')}</span>
			<button
				class="key-primary"
				disabled={options.pool.length === 0 || testing}
				title={t('addWord.testHint')}
				onclick={test}
			>
				▶ {t('punishment.test')}
			</button>
			<button
				class="key-danger"
				title={t('punishment.delete')}
				aria-label={t('punishment.delete')}
				onclick={onremove}>✕</button
			>
		</div>
		{#if error}<p class="text-xs text-danger">{error}</p>{/if}
		{#if outcome}
			<p class="text-xs {outcome.result === 'added' ? 'text-ok' : 'text-accent'}">
				{t(`addWord.result.${outcome.result}`, { word: outcome.word ?? '' })}
			</p>
		{/if}

		<label class="block space-y-1.5">
			<span class="label">{t('addWord.pool')}</span>
			<textarea
				class="block h-32 input w-full"
				spellcheck="false"
				placeholder={t('addWord.poolPlaceholder')}
				value={poolText}
				oninput={(e) => {
					// One handler sets both, so the effect above never sees them out of step
					poolText = e.currentTarget.value;
					options.pool = parse(poolText);
				}}></textarea>
			<span class="block text-xs {options.pool.length ? 'text-muted' : 'text-accent'}">
				{options.pool.length ? t('addWord.poolHint') : t('addWord.poolEmpty')}
			</span>
		</label>

		<div class="space-y-3 module">
			<div class="flex flex-wrap items-center gap-3">
				<span class="label">{t('addWord.detection')}</span>
				<Segmented bind:value={options.mode} options={modes} />
			</div>
			<div class="flex flex-wrap items-center gap-3">
				<span class="label">{t('word.display')}</span>
				<Segmented bind:value={options.display_mode} options={displayModes} />
			</div>
			<div class="space-y-2">
				<div class="flex flex-wrap items-center gap-3">
					<span class="label">{t('addWord.punishments')}</span>
					<Segmented bind:value={options.punishments_from} options={sources} />
				</div>
				<p class="text-xs text-muted">
					{t(
						options.punishments_from === 'trigger'
							? 'addWord.fromTriggerHint'
							: 'addWord.fromListHint'
					)}
				</p>
			</div>
		</div>

		{#if options.punishments_from === 'list'}
			<PunishmentPicker bind:selection={options.punishments} />
		{/if}

		<div class="space-y-3">
			<div class="flex flex-wrap items-center gap-3">
				<span class="label">{t('addWord.lifetime')}</span>
				<Segmented
					bind:value={
						() => (options.duration > 0 ? 'timed' : 'forever'),
						(value) => (options.duration = value === 'timed' ? DEFAULT_LIFETIME : 0)
					}
					options={lifetimes}
				/>
			</div>
			{#if options.duration > 0}
				<Slider
					bind:value={options.duration}
					label={t('addWord.removedAfter')}
					min={10}
					max={900}
					step={10}
					format={duration}
				/>
			{/if}
		</div>
	</div>
</article>
