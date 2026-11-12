<script lang="ts">
	import { onMount } from 'svelte';
	import { app } from '../app.svelte';
	import { api } from '../api';
	import { locales, t } from '../i18n.svelte';
	import type { Microphones, ScreenInfo } from '../types';
	import Segmented from '../ui/Segmented.svelte';
	import Toggle from '../ui/Toggle.svelte';

	const config = $derived(app.config!);

	let microphones = $state<Microphones | null>(null);
	let screens = $state<ScreenInfo[]>([]);
	let copied = $state(false);

	// Always the backend's address, even when the panel runs on the Vite dev server.
	const overlayUrl = 'http://localhost:8765/overlay/';

	onMount(async () => {
		[microphones, screens] = await Promise.all([api.microphones(), api.screens()]);
	});

	async function copyOverlayUrl() {
		await navigator.clipboard.writeText(overlayUrl);
		copied = true;
		setTimeout(() => (copied = false), 1500);
	}
</script>

<div class="space-y-6">
	<div>
		<h2 class="heading">{t('settings.title')}</h2>
		<p class="text-sm text-muted">{t('settings.subtitle')}</p>
	</div>

	<section class="space-y-4 panel pt-6">
		<h3 class="subheading">{t('settings.listening')}</h3>
		<label class="block space-y-1.5">
			<span class="label">{t('settings.microphone')}</span>
			<select
				class="input w-full"
				value={config.microphone ?? ''}
				onchange={(e) => (config.microphone = e.currentTarget.value || null)}
			>
				<option value="">
					{t('settings.defaultMicrophone')}{microphones?.default ? ` (${microphones.default})` : ''}
				</option>
				{#each microphones?.microphones ?? [] as mic (mic.id)}
					<option value={mic.id}>{mic.label}</option>
				{/each}
			</select>
			<span class="block text-xs text-muted">{t('settings.microphoneHint')}</span>
		</label>

		<label class="block space-y-1.5">
			<span class="label">{t('settings.cooldown')}</span>
			<span class="flex items-center gap-3">
				<input
					type="number"
					class="input w-20 text-accent"
					min="0"
					step="0.5"
					bind:value={config.cooldown}
				/>
				<span class="text-sm text-muted">{t('settings.cooldownHint')}</span>
			</span>
		</label>
	</section>

	<section class="space-y-4 panel pt-6">
		<div>
			<h3 class="subheading">{t('settings.screen')}</h3>
			<p class="text-xs text-accent">{t('settings.restartHint')}</p>
		</div>
		<Toggle
			bind:checked={config.display.screen.enabled}
			label={t('settings.screenEnabled')}
			hint={t('settings.screenEnabledHint')}
		/>
		<label class="block space-y-1.5">
			<span class="label">{t('settings.monitor')}</span>
			{#if screens.length}
				<select class="input w-full" bind:value={config.display.screen.monitor}>
					{#each screens as screen (screen.index)}
						<option value={screen.index}>
							{screen.index + 1}. {screen.name} — {screen.width}×{screen.height}{screen.primary
								? ` (${t('settings.primary')})`
								: ''}
						</option>
					{/each}
				</select>
			{:else}
				<input
					type="number"
					class="block input w-20 text-accent"
					min="0"
					bind:value={config.display.screen.monitor}
				/>
				<span class="block text-xs text-muted">{t('settings.monitorFallback')}</span>
			{/if}
		</label>
		<Toggle
			bind:checked={config.display.screen.sound}
			label={t('settings.screenSound')}
			hint={t('settings.screenSoundHint')}
		/>
		<Toggle
			bind:checked={config.display.screen.hide_from_capture}
			label={t('settings.hideFromCapture')}
			hint={t('settings.hideFromCaptureHint')}
		/>
	</section>

	<section class="space-y-4 panel pt-6">
		<h3 class="subheading">{t('settings.overlay')}</h3>
		<div class="space-y-1.5">
			<span class="label">{t('settings.overlayUrl')}</span>
			<div class="flex gap-2">
				<input class="flex-1 px-3 py-1.5 text-sm well" readonly value={overlayUrl} />
				<button class="key" onclick={copyOverlayUrl}>
					<span class={copied ? 'led-on' : 'led'}></span>
					{copied ? t('settings.copied') : t('settings.copy')}
				</button>
			</div>
			<span class="block text-xs text-muted">{t('settings.overlayUrlHint')}</span>
		</div>
		<Toggle
			bind:checked={config.display.overlay.sound}
			label={t('settings.overlaySound')}
			hint={t('settings.overlaySoundHint')}
		/>
	</section>

	<section class="space-y-3 panel pt-6">
		<h3 class="subheading">{t('settings.language')}</h3>
		<Segmented bind:value={config.language} options={locales} />
	</section>
</div>
