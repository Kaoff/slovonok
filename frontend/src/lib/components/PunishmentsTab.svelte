<script lang="ts">
	import { app } from '../app.svelte';
	import { newId } from '../api';
	import { t } from '../i18n.svelte';
	import type { MediaFile } from '../types';
	import MediaLibrary from './MediaLibrary.svelte';
	import PunishmentCard from './PunishmentCard.svelte';

	const config = $derived(app.config!);

	function addPunishment(media?: MediaFile) {
		config.punishments.push({
			id: newId('p'),
			name: media ? media.file.replace(/\.[^.]+$/, '') : '',
			type: media?.type ?? 'sound',
			file: media?.file ?? '',
			volume: 1,
			duration: 3,
			chroma_key: {
				enabled: false,
				color: '#00ff00',
				similarity: 0.4,
				smoothness: 0.08,
				spill: 0.1
			}
		});
	}

	function removePunishment(id: string) {
		const used = config.words.filter((w) => w.punishments.ids.includes(id));
		const words = used.map((w) => `« ${w.word} »`).join(', ');
		if (used.length && !confirm(t('punishments.confirmDelete', { words }))) return;
		for (const word of used) word.punishments.ids = word.punishments.ids.filter((i) => i !== id);
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
			<button class="key-primary" onclick={() => addPunishment()}>+ {t('punishments.add')}</button>
		</div>

		{#each config.punishments as punishment, i (punishment.id)}
			<PunishmentCard
				bind:punishment={config.punishments[i]}
				onremove={() => removePunishment(punishment.id)}
			/>
		{:else}
			<p class="panel text-center text-sm text-muted">{t('punishments.empty')}</p>
		{/each}
	</section>

	<MediaLibrary oncreate={addPunishment} />
</div>
