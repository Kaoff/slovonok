<!--
	Which punishments run, and how they are chosen (all / random / escalation).
	Used by a word, and by the "add a forbidden word" punishment for the words it creates.
-->
<script lang="ts">
	import { app } from '../app.svelte';
	import { t } from '../i18n.svelte';
	import type { PunishmentSelection, Strategy } from '../types';
	import Segmented from '../ui/Segmented.svelte';

	let { selection = $bindable() }: { selection: PunishmentSelection } = $props();

	const punishments = $derived(app.config!.punishments);
	const selected = $derived(
		selection.ids.map((id) => punishments.find((p) => p.id === id)).filter((p) => p !== undefined)
	);
	const available = $derived(punishments.filter((p) => !selection.ids.includes(p.id)));

	const strategies = $derived<{ value: Strategy; label: string }[]>([
		{ value: 'all', label: t('word.strategy.all') },
		{ value: 'random', label: t('word.strategy.random') },
		{ value: 'escalation', label: t('word.strategy.escalation') }
	]);
	const strategyHint = $derived(t(`word.strategy.${selection.strategy}Hint`));

	function addPunishment(e: Event) {
		const select = e.currentTarget as HTMLSelectElement;
		if (select.value) selection.ids.push(select.value);
		select.value = '';
	}

	function move(index: number, delta: number) {
		const [id] = selection.ids.splice(index, 1);
		selection.ids.splice(index + delta, 0, id);
	}
</script>

<section class="space-y-3">
	<div class="flex flex-wrap items-center gap-3">
		<h3 class="label text-base">{t('word.punishments')}</h3>
		<Segmented bind:value={selection.strategy} options={strategies} />
	</div>
	<p class="text-xs text-muted">{strategyHint}</p>

	<ol class="space-y-1.5">
		{#each selected as punishment, i (punishment.id)}
			<li class="flex items-center gap-2 module py-1.5 text-sm">
				{#if selection.strategy === 'escalation'}
					<span class="w-7 py-0.5 text-center text-xs well tabular-nums">{i + 1}</span>
				{/if}
				<span class="flex-1">{punishment.name || punishment.file}</span>
				<span class="label text-xs">{t(`type.${punishment.type}`)}</span>
				{#if selection.strategy === 'escalation'}
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
					onclick={() => selection.ids.splice(i, 1)}>✕</button
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
