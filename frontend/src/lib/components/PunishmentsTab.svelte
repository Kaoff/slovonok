<script lang="ts">
	import { app } from '../app.svelte';
	import { newId } from '../api';
	import { t } from '../i18n.svelte';
	import type { MediaFile, Punishment } from '../types';
	import MediaLibrary from './MediaLibrary.svelte';
	import AddWordCard from './AddWordCard.svelte';
	import PunishmentCard from './PunishmentCard.svelte';

	const config = $derived(app.config!);

	function addPunishment(media?: MediaFile) {
		config.punishments.push({
			...blank(),
			id: newId('p'),
			name: media ? media.file.replace(/\.[^.]+$/, '') : '',
			type: media?.type ?? 'sound',
			file: media?.file ?? ''
		});
	}

	function addWordPunishment() {
		config.punishments.push({ ...blank(), id: newId('p'), type: 'add_word' });
	}

	/** Every field of a punishment, whatever its type (the server keeps them all). */
	function blank(): Punishment {
		return {
			id: '',
			name: '',
			type: 'sound',
			file: '',
			volume: 1,
			duration: 3,
			chroma_key: {
				enabled: false,
				color: '#00ff00',
				similarity: 0.4,
				smoothness: 0.08,
				spill: 0.1
			},
			add_word: {
				pool: [],
				mode: 'phonetic',
				display_mode: 'shown',
				punishments_from: 'trigger',
				punishments: { strategy: 'all', ids: [] },
				duration: 0
			}
		};
	}

	function removePunishment(id: string) {
		const used = config.words.filter((w) => w.punishments.ids.includes(id));
		const words = used.map((w) => `« ${w.word} »`).join(', ');
		if (used.length && !confirm(t('punishments.confirmDelete', { words }))) return;
		for (const word of used) word.punishments.ids = word.punishments.ids.filter((i) => i !== id);
		for (const other of config.punishments) {
			const list = other.add_word.punishments;
			list.ids = list.ids.filter((i) => i !== id);
		}
		const index = config.punishments.findIndex((p) => p.id === id);
		if (index >= 0) config.punishments.splice(index, 1);
	}
</script>

<div class="space-y-10">
	<section class="space-y-5">
		<div class="flex items-end justify-between gap-4">
			<div>
				<h2 class="heading">{t('punishments.title')}</h2>
				<p class="text-sm text-muted">{t('punishments.subtitle')}</p>
			</div>
			<div class="flex flex-wrap gap-2">
				<button class="key-primary" onclick={() => addPunishment()}>+ {t('punishments.add')}</button
				>
				<button class="key" onclick={addWordPunishment}>+ {t('punishments.addWord')}</button>
			</div>
		</div>

		{#each config.punishments as punishment, i (punishment.id)}
			{#if punishment.type === 'add_word'}
				<AddWordCard
					bind:punishment={config.punishments[i]}
					onremove={() => removePunishment(punishment.id)}
				/>
			{:else}
				<PunishmentCard
					bind:punishment={config.punishments[i]}
					onremove={() => removePunishment(punishment.id)}
				/>
			{/if}
		{:else}
			<p class="panel text-center text-sm text-muted">{t('punishments.empty')}</p>
		{/each}
	</section>

	<MediaLibrary oncreate={addPunishment} />
</div>
