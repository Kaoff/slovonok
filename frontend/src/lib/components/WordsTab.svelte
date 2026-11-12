<script lang="ts">
	import { app } from '../app.svelte';
	import { newId } from '../api';
	import { t } from '../i18n.svelte';
	import WordCard from './WordCard.svelte';

	const config = $derived(app.config!);

	function addWord() {
		config.words.push({
			id: newId('w'),
			word: '',
			mode: 'phonetic',
			word_end: true,
			word_start: false,
			plural: true,
			enabled: true,
			count: 0,
			display_mode: 'shown',
			variants: [],
			tolerance: 0,
			auto: false,
			expires_at: null,
			punishments: { strategy: 'all', ids: [] }
		});
	}

	function removeWord(id: string) {
		app.dismissWord(id);
		const index = config.words.findIndex((w) => w.id === id);
		if (index >= 0) config.words.splice(index, 1);
	}
</script>

<div class="space-y-5">
	<div class="flex items-end justify-between gap-4">
		<div>
			<h2 class="heading">{t('words.title')}</h2>
			<p class="text-sm text-muted">{t('words.subtitle')}</p>
		</div>
		<button class="key-primary" onclick={addWord}>+ {t('words.add')}</button>
	</div>

	{#each config.words as word, i (word.id)}
		<WordCard bind:word={config.words[i]} onremove={() => removeWord(word.id)} />
	{:else}
		<p class="panel text-center text-sm text-muted">{t('words.empty')}</p>
	{/each}
</div>
