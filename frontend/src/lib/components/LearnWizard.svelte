<!--
	"Learn a word": the streamer says the word a few times and the app keeps what Vosk heard.
	Vosk only outputs French vocabulary, so an invented word comes out as its closest neighbours
	("pas quoi", "par quoi"…): each transcription kept becomes a "sounds like" variant of the word.

	While this window is open the server shows what is said but doesn't detect it, so repeating
	the word doesn't punish anyone. The panel tells it so every few seconds: if the panel dies,
	detection comes back by itself.
-->
<script lang="ts">
	import { app } from '../app.svelte';
	import { api } from '../api';
	import { t } from '../i18n.svelte';
	import type { Word } from '../types';
	import Toggle from '../ui/Toggle.svelte';

	let { open = $bindable(), word = $bindable() }: { open: boolean; word: Word } = $props();

	interface Take {
		key: string; // the transcription as heard, lowercased: identical takes are counted together
		text: string; // editable: trim it to the part that sounds like the word
		count: number;
		keep: boolean;
		touched: boolean; // the user chose: stop pre-checking it
	}

	const REFRESH_EVERY = 5000; // ms, the server's timeout is 15 s
	const PRECHECK_AT = 2; // heard this many times: probably the word, not a stray sentence

	let dialog = $state<HTMLDialogElement>();
	let takes = $state<Take[]>([]);
	// Per take, answered by the server: its sounds, and whether the word already catches it
	let sounds = $state<Record<string, string>>({});
	let detected = $state<Record<string, boolean>>({});
	let wordSounds = $state<string[]>([]); // the word's own sounds, then its variants'
	let error = $state<string | null>(null);

	$effect(() => {
		if (open && !dialog?.open) dialog?.showModal();
		else if (!open && dialog?.open) dialog.close();
	});

	// --- While open: pause detection and collect final transcriptions ---
	$effect(() => {
		if (!open) return;
		takes = [];
		const pause = () => api.setLearning(true).catch(() => {});
		pause();
		const timer = setInterval(pause, REFRESH_EVERY);
		const stopListening = app.listenFinals(hear);
		return () => {
			clearInterval(timer);
			stopListening();
			api.setLearning(false).catch(() => {});
		};
	});

	function hear(text: string) {
		const key = text.trim().toLowerCase();
		if (!key) return;
		const take = takes.find((tk) => tk.key === key);
		if (take) {
			take.count++;
			if (!take.touched && take.count >= PRECHECK_AT) take.keep = true;
		} else {
			takes.push({ key, text: text.trim(), count: 1, keep: false, touched: false });
		}
	}

	// --- Sounds and "already detected", asked to the server (debounced, latest answer wins) ---
	let generation = 0;
	$effect(() => {
		if (!open) return;
		const texts = takes.map((tk) => tk.text);
		const request = {
			word: word.word,
			mode: word.mode,
			word_start: word.word_start,
			word_end: word.word_end,
			plural: word.plural,
			variants: $state.snapshot(word.variants),
			tolerance: word.tolerance,
			texts
		};
		const mine = ++generation;
		const timer = setTimeout(async () => {
			try {
				const [phonemes, match] = await Promise.all([
					api.phonemize([word.word, ...word.variants, ...texts]),
					texts.length ? api.match(request) : { matches: [] }
				]);
				if (mine !== generation) return;
				const own = 1 + word.variants.length;
				wordSounds = phonemes.sounds.slice(0, own).filter(Boolean);
				sounds = Object.fromEntries(texts.map((text, i) => [text, phonemes.sounds[own + i]]));
				detected = Object.fromEntries(texts.map((text, i) => [text, match.matches[i]]));
				error = null;
			} catch (e) {
				if (mine === generation) error = (e as Error).message;
			}
		}, 250);
		return () => clearTimeout(timer);
	});

	/** Already caught by the word (or its variants), or sounding exactly like it: no need to add. */
	const redundant = (take: Take) =>
		detected[take.text] || (sounds[take.text] && wordSounds.includes(sounds[take.text]));

	const chosen = $derived(takes.filter((tk) => tk.keep && tk.text.trim() && !redundant(tk)));

	function save() {
		const known = word.variants.map((v) => v.trim().toLowerCase());
		for (const take of chosen) {
			const text = take.text.trim();
			if (known.includes(text.toLowerCase())) continue;
			known.push(text.toLowerCase());
			word.variants.push(text);
		}
		open = false;
	}
</script>

<dialog
	bind:this={dialog}
	onclose={() => (open = false)}
	aria-label={t('learn.title', { word: word.word })}
	class="m-auto max-h-[90dvh] w-[min(56rem,94dvw)] bg-surface p-0 text-fg recess backdrop:bg-black/80"
>
	{#if open}
		<div class="flex max-h-[90dvh] flex-col gap-4 overflow-auto p-5">
			<header class="flex flex-wrap items-center gap-3">
				<h2 class="flex-1 heading">{t('learn.title', { word: word.word })}</h2>
				<button
					class="key-danger"
					title={t('learn.close')}
					aria-label={t('learn.close')}
					onclick={() => (open = false)}>✕</button
				>
			</header>

			<p class="text-sm">{t('learn.intro')}</p>
			<p class="text-xs text-accent">{t('learn.paused')}</p>
			{#if error}<p class="text-xs text-danger">{error}</p>{/if}
			{#if !app.status?.listening}
				<p class="text-xs text-danger">{t('learn.notListening')}</p>
			{/if}

			{#if wordSounds.length}
				<p class="text-xs text-muted">
					{t('learn.target')}
					<span class="text-accent">/{wordSounds[0]}/</span>
				</p>
			{/if}

			{#if takes.length === 0}
				<p class="module text-center text-sm text-muted">{t('learn.waiting')}</p>
			{:else}
				<ul class="space-y-1.5">
					{#each takes as take (take.key)}
						<li class="flex flex-wrap items-center gap-3 module py-2">
							<Toggle
								bind:checked={take.keep}
								title={t('learn.keep')}
								onchange={() => (take.touched = true)}
							/>
							<input
								class="input min-w-48 flex-1"
								aria-label={t('learn.take')}
								bind:value={take.text}
							/>
							<span
								class="w-10 text-center text-xs text-muted tabular-nums"
								title={t('learn.times')}
							>
								×{take.count}
							</span>
							<span class="w-40 truncate text-xs text-muted" title={sounds[take.text]}>
								{sounds[take.text] ? `/${sounds[take.text]}/` : ''}
							</span>
							<span class="w-40 text-xs text-accent">
								{#if detected[take.text]}{t('learn.detected')}
								{:else if redundant(take)}{t('learn.same')}{/if}
							</span>
						</li>
					{/each}
				</ul>
				<p class="text-xs text-muted">{t('learn.trimHint')}</p>
			{/if}

			<p class="text-xs text-muted">{t('word.falsePositives')}</p>

			<footer class="flex flex-wrap items-center justify-end gap-2">
				<button class="key text-xs" disabled={takes.length === 0} onclick={() => (takes = [])}>
					{t('learn.clear')}
				</button>
				<button class="key-primary" disabled={chosen.length === 0} onclick={save}>
					{t('learn.save', { count: chosen.length })}
				</button>
			</footer>
		</div>
	{/if}
</dialog>
