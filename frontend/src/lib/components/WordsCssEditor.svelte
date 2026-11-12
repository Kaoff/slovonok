<!--
	Full-screen editor for the words overlay's custom CSS: live preview on the left, code on the
	right. A native modal <dialog>: it sits above the whole panel, keeps focus inside, Esc closes it.
	Edits go straight into the config (auto-saved like everything else).
-->
<script lang="ts">
	import { app } from '../app.svelte';
	import { t } from '../i18n.svelte';
	import CssEditor from '../ui/CssEditor.svelte';
	import WordsPreview from './WordsPreview.svelte';

	let { open = $bindable() }: { open: boolean } = $props();

	let dialog = $state<HTMLDialogElement>();
	let preview = $state<WordsPreview>();
	let cssError = $state(false);

	const words = $derived(app.config!.display.words);

	$effect(() => {
		if (open && !dialog?.open) dialog?.showModal();
		else if (!open && dialog?.open) dialog.close();
	});

	/** Starts from the built-in look (the same file the overlay loads without custom CSS). */
	async function insertDefaultCss() {
		if (words.custom_css.trim() && !confirm(t('settings.wordsCssDefaultConfirm'))) return;
		try {
			const response = await fetch('/overlay/words/default.css');
			if (!response.ok) throw new Error(String(response.status));
			words.custom_css = await response.text();
			cssError = false;
		} catch {
			cssError = true;
		}
	}

	const plays = $derived([
		{ kind: 'enter', label: t('settings.wordsEnter'), name: words.enter_animation },
		{ kind: 'hit', label: t('settings.wordsHit'), name: words.hit_animation },
		{ kind: 'exit', label: t('settings.wordsExit'), name: words.exit_animation }
	] as const);
</script>

<dialog
	bind:this={dialog}
	onclose={() => (open = false)}
	aria-label={t('settings.wordsCss')}
	class="m-0 h-dvh max-h-none w-dvw max-w-none bg-surface p-0 text-fg backdrop:bg-black/80"
>
	{#if open}
		<div class="flex h-full flex-col gap-4 p-5">
			<header class="flex flex-wrap items-center gap-3">
				<h2 class="flex-1 heading">{t('settings.wordsCss')}</h2>
				<button class="key text-xs" onclick={insertDefaultCss}
					>{t('settings.wordsCssDefault')}</button
				>
				<button
					class="key-danger"
					title={t('settings.wordsCssClose')}
					aria-label={t('settings.wordsCssClose')}
					onclick={() => (open = false)}>✕</button
				>
			</header>

			<div class="grid min-h-0 flex-1 gap-5 lg:grid-cols-2">
				<section class="flex min-h-0 flex-col gap-3 overflow-auto">
					<WordsPreview bind:this={preview} />
					<div class="flex flex-wrap items-center gap-2">
						<span class="label">{t('settings.wordsAnimations')}</span>
						{#each plays as play (play.kind)}
							<button
								class="key text-xs"
								disabled={play.name === 'none'}
								onclick={() => preview?.play(play.kind, play.name)}
							>
								{play.label} · {t(`anim.${play.name}`)}
							</button>
						{/each}
					</div>
					<p class="text-xs text-muted">{t('settings.wordsCssHint')}</p>
				</section>

				<section class="flex min-h-0 flex-col gap-1.5">
					<CssEditor bind:value={words.custom_css} label={t('settings.wordsCss')} />
					{#if cssError}
						<span class="text-xs text-danger">{t('settings.wordsCssDefaultError')}</span>
					{/if}
				</section>
			</div>
		</div>
	{/if}
</dialog>
