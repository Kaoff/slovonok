<script lang="ts">
	import { app } from '../app.svelte';
	import { api, mediaUrl } from '../api';
	import { t } from '../i18n.svelte';
	import type { Punishment } from '../types';
	import Slider from '../ui/Slider.svelte';
	import Toggle from '../ui/Toggle.svelte';

	let { punishment = $bindable(), onremove }: { punishment: Punishment; onremove: () => void } =
		$props();

	let testing = $state(false);
	let error = $state<string | null>(null);

	const missing = $derived(
		punishment.file !== '' && !app.media.some((m) => m.file === punishment.file)
	);
	const percent = (v: number) => `${Math.round(v * 100)} %`;
	const decimal = (v: number) => v.toFixed(2);

	function selectFile(e: Event) {
		const file = (e.currentTarget as HTMLSelectElement).value;
		const media = app.media.find((m) => m.file === file);
		punishment.file = file;
		if (media) punishment.type = media.type;
		if (media && !punishment.name) punishment.name = file.replace(/\.[^.]+$/, '');
	}

	async function test() {
		testing = true;
		error = null;
		try {
			await app.flush(); // the overlay must play the latest settings
			await api.testPunishment(punishment.id);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			testing = false;
		}
	}
</script>

<article class="grid gap-5 panel pt-6 md:grid-cols-[11rem_1fr]">
	<!-- Preview monitor -->
	<div class="flex aspect-video items-center justify-center overflow-hidden p-1 recess">
		<div
			class="flex h-full w-full items-center justify-center bg-[repeating-conic-gradient(#0a1014_0_25%,#111a20_0_50%)] bg-size-[0.875rem_0.875rem]"
		>
			{#if !punishment.file}
				<span class="label text-xs">{t('punishment.noFile')}</span>
			{:else if punishment.type === 'image'}
				<img src={mediaUrl(punishment.file)} alt="" class="max-h-full max-w-full object-contain" />
			{:else if punishment.type === 'video'}
				<video
					src={mediaUrl(punishment.file)}
					class="max-h-full max-w-full"
					muted
					preload="metadata"
				></video>
			{:else}
				<span class="text-2xl text-accent" aria-hidden="true">♪</span>
			{/if}
		</div>
	</div>

	<div class="space-y-4">
		<div class="flex flex-wrap items-center gap-2">
			<input
				class="input min-w-40 flex-1 text-lg font-strong tracking-wide"
				placeholder={t('punishment.name')}
				aria-label={t('punishment.name')}
				bind:value={punishment.name}
			/>
			<select class="input max-w-64" value={punishment.file} onchange={selectFile}>
				<option value="" disabled>{t('punishment.chooseFile')}</option>
				{#each app.media as media (media.file)}
					<option value={media.file}>{media.file}</option>
				{/each}
				{#if missing}
					<option value={punishment.file}>{punishment.file} ({t('punishment.missing')})</option>
				{/if}
			</select>
			<button class="key-primary" disabled={!punishment.file || testing} onclick={test}>
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
		{#if missing}<p class="text-xs text-accent">{t('punishment.missingHint')}</p>{/if}

		<div class="grid gap-4 sm:grid-cols-2">
			{#if punishment.type !== 'image'}
				<Slider
					bind:value={punishment.volume}
					label={t('punishment.volume')}
					min={0}
					max={1}
					step={0.05}
					format={percent}
				/>
			{:else}
				<Slider
					bind:value={punishment.duration}
					label={t('punishment.duration')}
					min={0.5}
					max={15}
					step={0.5}
					format={(v) => `${v} s`}
				/>
			{/if}
		</div>

		{#if punishment.type !== 'sound'}
			<div class="space-y-3 module">
				<div class="flex flex-wrap items-center gap-4">
					<Toggle
						bind:checked={punishment.chroma_key.enabled}
						label={t('punishment.chromaKey')}
						hint={t('punishment.chromaKeyEnabled')}
					/>
					<input
						type="color"
						class="h-8 w-12 cursor-pointer p-1 recess disabled:opacity-40"
						aria-label={t('punishment.chromaKey')}
						bind:value={punishment.chroma_key.color}
						disabled={!punishment.chroma_key.enabled}
					/>
				</div>
				{#if punishment.chroma_key.enabled}
					<div class="grid gap-4 sm:grid-cols-3">
						<Slider
							bind:value={punishment.chroma_key.similarity}
							label={t('punishment.similarity')}
							min={0}
							max={1}
							step={0.01}
							format={decimal}
						/>
						<Slider
							bind:value={punishment.chroma_key.smoothness}
							label={t('punishment.smoothness')}
							min={0}
							max={0.5}
							step={0.01}
							format={decimal}
						/>
						<Slider
							bind:value={punishment.chroma_key.spill}
							label={t('punishment.spill')}
							min={0}
							max={0.5}
							step={0.01}
							format={decimal}
						/>
					</div>
					<p class="text-xs text-muted">{t('punishment.chromaKeyHint')}</p>
				{/if}
			</div>
		{/if}
	</div>
</article>
