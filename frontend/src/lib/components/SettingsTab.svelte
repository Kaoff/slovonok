<script lang="ts">
	import { onMount } from 'svelte';
	import { app } from '../app.svelte';
	import { api } from '../api';
	import { i18n, locales, t } from '../i18n.svelte';
	import type { Microphones, ScreenInfo, WordsAlign, WordsPosition } from '../types';
	import Segmented from '../ui/Segmented.svelte';
	import Slider from '../ui/Slider.svelte';
	import Toggle from '../ui/Toggle.svelte';
	import WordsCssEditor from './WordsCssEditor.svelte';
	import WordsPreview from './WordsPreview.svelte';

	const config = $derived(app.config!);

	// --- Updates ---
	const update = $derived(app.update);
	const busy = $derived(update !== null && update.stage !== 'idle');
	let updateError = $state<string | null>(null);

	async function checkUpdate() {
		updateError = null;
		try {
			app.update = await api.checkUpdate();
		} catch (e) {
			updateError = (e as Error).message;
		}
	}

	async function installUpdate() {
		updateError = null;
		try {
			app.update = await api.installUpdate();
		} catch (e) {
			updateError = (e as Error).message;
		}
	}

	const megabytes = (bytes: number) => `${(bytes / 1_000_000).toFixed(0)} MB`;
	const clock = (unixSeconds: number) =>
		new Date(unixSeconds * 1000).toLocaleTimeString(i18n.locale, {
			hour: '2-digit',
			minute: '2-digit'
		});

	let microphones = $state<Microphones | null>(null);
	let screens = $state<ScreenInfo[]>([]);
	let copied = $state(false);
	let wordsCopied = $state(false);

	// Always the backend's address, even when the panel runs on the Vite dev server.
	const overlayUrl = 'http://localhost:8765/overlay/';
	const wordsOverlayUrl = 'http://localhost:8765/overlay/words/';

	const enterAnimations = ['none', 'fade', 'slide', 'pop', 'glitch'] as const;
	const exitAnimations = ['none', 'fade', 'slide', 'shrink', 'glitch'] as const;
	const hitAnimations = ['none', 'shake', 'pulse', 'flash', 'glitch'] as const;

	let preview = $state<WordsPreview>();
	let editorOpen = $state(false);

	const alignments = $derived<{ value: WordsAlign; label: string }[]>([
		{ value: 'left', label: t('settings.align.left') },
		{ value: 'center', label: t('settings.align.center') },
		{ value: 'right', label: t('settings.align.right') }
	]);
	const positions = $derived<{ value: WordsPosition; label: string }[]>([
		{ value: 'top', label: t('settings.position.top') },
		{ value: 'middle', label: t('settings.position.middle') },
		{ value: 'bottom', label: t('settings.position.bottom') }
	]);

	onMount(async () => {
		[microphones, screens] = await Promise.all([api.microphones(), api.screens()]);
	});

	async function copyOverlayUrl() {
		await navigator.clipboard.writeText(overlayUrl);
		copied = true;
		setTimeout(() => (copied = false), 1500);
	}

	async function copyWordsOverlayUrl() {
		await navigator.clipboard.writeText(wordsOverlayUrl);
		wordsCopied = true;
		setTimeout(() => (wordsCopied = false), 1500);
	}
</script>

<div class="space-y-5">
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
			<span class="label">{t('settings.maxWords')}</span>
			<span class="flex items-center gap-3">
				<input
					type="number"
					class="input w-20 text-accent"
					min="0"
					step="1"
					bind:value={config.max_active_words}
				/>
				<span class="text-sm text-muted">{t('settings.maxWordsHint')}</span>
			</span>
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
		<h3 class="subheading">{t('settings.screen')}</h3>
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

	<section class="space-y-4 panel pt-6">
		<h3 class="subheading">{t('settings.wordsOverlay')}</h3>
		<div class="space-y-1.5">
			<span class="label">{t('settings.overlayUrl')}</span>
			<div class="flex gap-2">
				<input class="flex-1 px-3 py-1.5 text-sm well" readonly value={wordsOverlayUrl} />
				<button class="key" onclick={copyWordsOverlayUrl}>
					<span class={wordsCopied ? 'led-on' : 'led'}></span>
					{wordsCopied ? t('settings.copied') : t('settings.copy')}
				</button>
			</div>
			<span class="block text-xs text-muted">{t('settings.wordsOverlayHint')}</span>
		</div>
		<div class="space-y-1.5">
			<span class="label">{t('settings.wordsPreview')}</span>
			<WordsPreview bind:this={preview} />
			<span class="block text-xs text-muted">{t('settings.wordsPreviewHint')}</span>
		</div>

		<fieldset class="space-y-3">
			<legend class="mb-2 label">{t('settings.wordsAnimations')}</legend>
			{#each [{ kind: 'enter', label: t('settings.wordsEnter'), names: enterAnimations }, { kind: 'hit', label: t('settings.wordsHit'), names: hitAnimations }, { kind: 'exit', label: t('settings.wordsExit'), names: exitAnimations }] as const as row (row.kind)}
				{@const key = `${row.kind}_animation` as const}
				<div class="flex items-center gap-3">
					<span class="w-32 text-sm">{row.label}</span>
					<select
						class="input flex-1"
						value={config.display.words[key]}
						onchange={(e) => {
							// @ts-expect-error each row has its own union of names
							config.display.words[key] = e.currentTarget.value;
							preview?.play(row.kind, e.currentTarget.value);
						}}
					>
						{#each row.names as name (name)}
							<option value={name}>{t(`anim.${name}`)}</option>
						{/each}
					</select>
					<button
						class="key text-xs"
						disabled={config.display.words[key] === 'none'}
						onclick={() => preview?.play(row.kind, config.display.words[key])}
						>{t('settings.wordsPlay')}</button
					>
				</div>
			{/each}
		</fieldset>

		<Toggle
			bind:checked={config.display.words.custom_css_enabled}
			label={t('settings.wordsCssEnabled')}
			hint={t('settings.wordsCssEnabledHint')}
		/>

		{#if config.display.words.custom_css_enabled}
			<div class="flex flex-wrap items-center gap-3">
				<button class="key" onclick={() => (editorOpen = true)}
					>{t('settings.wordsCustomize')}</button
				>
				<span class="text-xs text-muted">{t('settings.wordsCustomizeHint')}</span>
			</div>
		{:else}
			<!-- The built-in look: these settings only feed variables of default.css -->
			<Slider
				bind:value={config.display.words.font_size}
				label={t('settings.wordsFontSize')}
				min={1}
				max={5}
				step={0.25}
				format={(v) => `${v} rem`}
			/>
			<label class="flex items-center gap-3">
				<span class="label">{t('settings.wordsColor')}</span>
				<input
					type="color"
					class="h-8 w-12 cursor-pointer p-1 recess"
					bind:value={config.display.words.color}
				/>
			</label>
			<div class="flex flex-wrap items-center gap-x-8 gap-y-3">
				<div class="space-y-1.5">
					<span class="label">{t('settings.wordsAlign')}</span>
					<Segmented bind:value={config.display.words.align} options={alignments} />
				</div>
				<div class="space-y-1.5">
					<span class="label">{t('settings.wordsPosition')}</span>
					<Segmented bind:value={config.display.words.position} options={positions} />
				</div>
			</div>
			<Toggle bind:checked={config.display.words.show_count} label={t('settings.wordsShowCount')} />
		{/if}
	</section>

	<section class="space-y-4 panel pt-6">
		<h3 class="subheading">{t('settings.updates')}</h3>
		<p class="text-sm">{t('settings.version', { version: update?.current ?? '…' })}</p>

		{#if update?.stage === 'downloading'}
			<div class="space-y-1.5">
				<p class="text-sm text-accent">
					{t('settings.updateDownloading', { percent: Math.round(update.progress * 100) })}
				</p>
				<div
					class="h-2 recess"
					role="progressbar"
					aria-valuenow={Math.round(update.progress * 100)}
				>
					<div class="h-full bg-accent" style:width="{update.progress * 100}%"></div>
				</div>
			</div>
		{:else if update?.stage === 'installing'}
			<p class="text-sm text-accent">{t('settings.updateInstalling')}</p>
		{:else if update?.available}
			<div class="space-y-2 module">
				<p class="text-sm font-strong text-accent">
					{t('settings.updateAvailable', { version: update.latest ?? '' })}
					{#if update.size}<span class="font-normal text-muted">({megabytes(update.size)})</span
						>{/if}
				</p>
				{#if update.notes}
					<p class="max-h-48 overflow-y-auto text-xs whitespace-pre-wrap text-muted">
						{update.notes}
					</p>
				{/if}
				{#if update.can_install}
					<button class="key-primary" disabled={busy} onclick={installUpdate}>
						{t('settings.updateInstall')}
					</button>
					<p class="text-xs text-muted">{t('settings.updateInstallHint')}</p>
				{:else}
					<p class="text-xs text-muted">{t('settings.updateDevHint')}</p>
				{/if}
			</div>
		{:else if update?.last_checked && !update.error}
			<p class="text-sm text-muted">
				{t('settings.updateUpToDate', { time: clock(update.last_checked) })}
			</p>
		{/if}

		{#if update?.error || updateError}
			<p class="text-xs text-danger">
				{t('settings.updateError', { error: updateError ?? update?.error ?? '' })}
			</p>
		{/if}

		<button class="key" disabled={busy} onclick={checkUpdate}>
			{update?.stage === 'checking' ? t('settings.updateChecking') : t('settings.updateCheck')}
		</button>
	</section>

	<section class="space-y-3 panel pt-6">
		<h3 class="subheading">{t('settings.language')}</h3>
		<Segmented bind:value={config.language} options={locales} />
	</section>
</div>

<WordsCssEditor bind:open={editorOpen} />
