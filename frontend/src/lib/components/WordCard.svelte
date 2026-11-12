<script lang="ts">
	import { app } from '../app.svelte';
	import { api } from '../api';
	import { t } from '../i18n.svelte';
	import type { Mode, Strategy, Word } from '../types';
	import Segmented from '../ui/Segmented.svelte';
	import Toggle from '../ui/Toggle.svelte';

	let { word = $bindable(), onremove }: { word: Word; onremove: () => void } = $props();

	const punishments = $derived(app.config!.punishments);
	const selected = $derived(
		word.punishments.ids
			.map((id) => punishments.find((p) => p.id === id))
			.filter((p) => p !== undefined)
	);
	const available = $derived(punishments.filter((p) => !word.punishments.ids.includes(p.id)));

	const modes = $derived<{ value: Mode; label: string }[]>([
		{ value: 'phonetic', label: t('word.phonetic') },
		{ value: 'exact', label: t('word.exact') }
	]);
	const strategies = $derived<{ value: Strategy; label: string }[]>([
		{ value: 'all', label: t('word.strategy.all') },
		{ value: 'random', label: t('word.strategy.random') },
		{ value: 'escalation', label: t('word.strategy.escalation') }
	]);
	const strategyHint = $derived(t(`word.strategy.${word.punishments.strategy}Hint`));

	function addPunishment(e: Event) {
		const select = e.currentTarget as HTMLSelectElement;
		if (select.value) word.punishments.ids.push(select.value);
		select.value = '';
	}

	function move(index: number, delta: number) {
		const ids = word.punishments.ids;
		const [id] = ids.splice(index, 1);
		ids.splice(index + delta, 0, id);
	}

	function confirmRemove() {
		if (!word.word || confirm(t('word.confirmDelete', { word: word.word }))) onremove();
	}
</script>

<article class="space-y-4 panel pt-6 {word.enabled ? '' : 'saturate-50'}">
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
			<span class="min-w-12 well px-2 py-1 text-center text-lg tabular-nums">{word.count}</span>
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

	<section class="space-y-3">
		<div class="flex flex-wrap items-center gap-3">
			<h3 class="label text-base">{t('word.punishments')}</h3>
			<Segmented bind:value={word.punishments.strategy} options={strategies} />
		</div>
		<p class="text-xs text-muted">{strategyHint}</p>

		<ol class="space-y-1.5">
			{#each selected as punishment, i (punishment.id)}
				<li class="flex items-center gap-2 module py-1.5 text-sm">
					{#if word.punishments.strategy === 'escalation'}
						<span class="w-7 well py-0.5 text-center text-xs tabular-nums">{i + 1}</span>
					{/if}
					<span class="flex-1">{punishment.name || punishment.file}</span>
					<span class="label text-xs">{t(`type.${punishment.type}`)}</span>
					{#if word.punishments.strategy === 'escalation'}
						<button
							class="key px-2 py-1"
							title={t('word.moveUp')}
							aria-label={t('word.moveUp')}
							disabled={i === 0}
							onclick={() => move(i, -1)}>↑</button
						>
						<button
							class="key px-2 py-1"
							title={t('word.moveDown')}
							aria-label={t('word.moveDown')}
							disabled={i === selected.length - 1}
							onclick={() => move(i, 1)}>↓</button
						>
					{/if}
					<button
						class="key-danger py-1"
						title={t('word.remove')}
						aria-label={t('word.remove')}
						onclick={() => word.punishments.ids.splice(i, 1)}>✕</button
					>
				</li>
			{/each}
		</ol>

		{#if available.length > 0}
			<select class="input" onchange={addPunishment}>
				<option value="">+ {t('word.addPunishment')}</option>
				{#each available as punishment (punishment.id)}
					<option value={punishment.id}>{punishment.name || punishment.file}</option>
				{/each}
			</select>
		{:else if punishments.length === 0}
			<p class="text-xs text-muted">{t('word.noPunishments')}</p>
		{/if}
	</section>
</article>
