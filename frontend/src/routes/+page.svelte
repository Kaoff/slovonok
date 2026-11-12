<script lang="ts">
	import { onMount } from 'svelte';
	import { app } from '../lib/app.svelte';
	import { i18n, t, type MessageKey } from '../lib/i18n.svelte';
	import LivePanel from '../lib/components/LivePanel.svelte';
	import PunishmentsTab from '../lib/components/PunishmentsTab.svelte';
	import SettingsTab from '../lib/components/SettingsTab.svelte';
	import WordsTab from '../lib/components/WordsTab.svelte';
	import CrtToggle from '../lib/dev/CrtToggle.svelte';

	type Tab = 'words' | 'punishments' | 'settings';
	const tabs: { id: Tab; label: MessageKey }[] = [
		{ id: 'words', label: 'nav.words' },
		{ id: 'punishments', label: 'nav.punishments' },
		{ id: 'settings', label: 'nav.settings' }
	];
	let tab = $state<Tab>('words');
	let loadError = $state<string | null>(null);

	onMount(() => {
		app.init().catch((e: Error) => (loadError = e.message));
	});

	// Auto-save: any change to the config (deep) schedules a save.
	$effect(() => {
		if (!app.config) return;
		JSON.stringify(app.config); // reads every property, so the effect tracks them all
		app.configChanged();
	});

	// The language is part of the config.
	$effect(() => {
		if (app.config) i18n.locale = app.config.language;
	});
	$effect(() => {
		document.documentElement.lang = i18n.locale;
	});
</script>

<svelte:head><title>Slovonok</title></svelte:head>

<a
	href="#content"
	class="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50"
>
	<span class="key-primary">{t('app.skip')}</span>
</a>

<!-- Capped width so very wide screens keep the three columns together -->
<div class="mx-auto flex h-dvh max-w-[100rem] gap-4 p-4">
	<!-- Sidebar: name, sections, save state -->
	<header class="flex min-h-0 w-52 shrink-0 flex-col gap-8 overflow-y-auto panel px-4 py-6">
		<h1 class="flex items-center gap-2 heading text-lg leading-tight">
			<span class="led-on size-2.5"></span>Slovonok
		</h1>

		<nav aria-label={t('nav.label')}>
			<ul class="space-y-1">
				{#each tabs as item (item.id)}
					{@const active = tab === item.id}
					<li>
						<button
							class="nav-item {active ? 'nav-item-active' : ''}"
							aria-current={active ? 'page' : undefined}
							onclick={() => (tab = item.id)}
						>
							<span aria-hidden="true" class="w-3">{active ? '>' : ''}</span>
							{t(item.label)}
						</button>
					</li>
				{/each}
			</ul>
		</nav>

		{#if app.update?.available}
			<button
				class="nav-item border-accent text-accent"
				title={t('update.banner', { version: app.update.latest ?? '' })}
				onclick={() => (tab = 'settings')}
			>
				<span aria-hidden="true" class="w-3">↑</span>
				{t('update.banner', { version: app.update.latest ?? '' })}
			</button>
		{/if}

		<div class="mt-auto space-y-4">
			{#if import.meta.env.DEV}<CrtToggle />{/if}

			<p
				class="flex items-center gap-2 text-xs font-strong {app.saveState === 'error'
					? 'text-danger'
					: 'text-muted'}"
				title={app.saveError ?? ''}
			>
				<span
					class={app.saveState === 'error'
						? 'led-red'
						: app.saveState === 'saved'
							? 'led-green'
							: 'led-on'}
				></span>
				{t(`save.${app.saveState}`)}
			</p>
		</div>
	</header>

	<main id="content" tabindex="-1" class="min-w-0 flex-1 overflow-y-auto">
		<div class="px-2 pb-8">
			{#if loadError}
				<p class="panel text-danger">{t('app.unreachable', { error: loadError })}</p>
			{:else if !app.config}
				<p class="text-muted">{t('app.loading')}</p>
			{:else if tab === 'words'}
				<WordsTab />
			{:else if tab === 'punishments'}
				<PunishmentsTab />
			{:else}
				<SettingsTab />
			{/if}
		</div>
	</main>

	<aside class="flex min-h-0 w-80 shrink-0 flex-col gap-4">
		<LivePanel />
	</aside>
</div>
