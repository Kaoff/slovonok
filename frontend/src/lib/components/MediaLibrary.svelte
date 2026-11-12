<script lang="ts">
	import { app } from '../app.svelte';
	import { api } from '../api';
	import { t } from '../i18n.svelte';
	import type { MediaFile } from '../types';

	let { oncreate }: { oncreate: (media: MediaFile) => void } = $props();

	let uploading = $state(false);
	let error = $state<string | null>(null);
	let dragging = $state(false);

	const size = (bytes: number) =>
		bytes < 1024 * 1024
			? `${Math.round(bytes / 1024)} KB`
			: `${(bytes / 1024 / 1024).toFixed(1)} MB`;

	async function upload(files: FileList | null | undefined) {
		if (!files?.length) return;
		uploading = true;
		error = null;
		try {
			for (const file of files) await api.uploadMedia(file);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			uploading = false;
			await app.refreshMedia();
		}
	}

	async function remove(file: string) {
		if (!confirm(t('media.confirmDelete', { file }))) return;
		error = null;
		try {
			await api.deleteMedia(file);
			await app.refreshMedia();
		} catch (e) {
			error = (e as Error).message;
		}
	}

	function drop(e: DragEvent) {
		e.preventDefault();
		dragging = false;
		upload(e.dataTransfer?.files);
	}
</script>

<section class="space-y-4 panel pt-6">
	<div>
		<h2 class="heading">{t('media.title')}</h2>
		<p class="text-sm text-muted">{t('media.subtitle')}</p>
	</div>

	<label
		class="relative flex cursor-pointer flex-col items-center justify-center gap-1 px-4 py-6 text-sm recess transition {dragging
			? 'outline-2 outline-accent'
			: ''}"
		ondragover={(e) => {
			e.preventDefault();
			dragging = true;
		}}
		ondragleave={() => (dragging = false)}
		ondrop={drop}
	>
		<span class="flex items-center gap-2">
			<span class={uploading || dragging ? 'led-on' : 'led'}></span>
			{uploading ? t('media.uploading') : t('media.drop')}
		</span>
		<span class="text-xs text-muted">{t('media.formats')}</span>
		<input
			type="file"
			multiple
			class="sr-only"
			accept="audio/*,video/*,image/*"
			onchange={(e) => upload(e.currentTarget.files)}
		/>
	</label>
	{#if error}<p class="text-sm text-danger">{error}</p>{/if}

	<ul class="space-y-1.5">
		{#each app.media as media (media.file)}
			<li class="flex items-center gap-3 module py-1.5 text-sm">
				<span class="w-14 label text-xs">{t(`type.${media.type}`)}</span>
				<span class="flex-1 truncate">{media.file}</span>
				<span class="text-xs text-muted tabular-nums">{size(media.size)}</span>
				<button class="key text-xs" onclick={() => oncreate(media)}>+ {t('media.create')}</button>
				<button
					class="key-danger py-1"
					title={t('media.delete')}
					aria-label={t('media.delete')}
					onclick={() => remove(media.file)}>✕</button
				>
			</li>
		{:else}
			<li class="text-sm text-muted">{t('media.empty')}</li>
		{/each}
	</ul>
</section>
