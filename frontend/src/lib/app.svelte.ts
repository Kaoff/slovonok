import { api } from './api';
import { i18n } from './i18n.svelte';
import type { Config, MediaFile, ServerEvent, Status, Word } from './types';

type SaveState = 'saved' | 'pending' | 'saving' | 'error';

interface TranscriptLine {
	id: number;
	text: string;
	final: boolean;
}

interface Detection {
	id: number;
	word: string;
	count: number;
	at: Date;
}

const SAVE_DELAY = 500;
const MAX_LINES = 50;

/** Config without word counters: counters change on their own and are never "edited". */
function serialize(config: Config): string {
	return JSON.stringify({
		...config,
		words: config.words.map((word) => ({ ...word, count: 0 }))
	});
}

class AppState {
	config = $state<Config | null>(null);
	status = $state<Status | null>(null);
	media = $state<MediaFile[]>([]);
	connected = $state(false);
	saveState = $state<SaveState>('saved');
	saveError = $state<string | null>(null);
	transcript = $state<TranscriptLine[]>([]);
	detections = $state<Detection[]>([]);

	#savedJson = '';
	#saveTimer: ReturnType<typeof setTimeout> | undefined;
	#savePromise: Promise<void> | null = null;
	#nextId = 0;

	async init() {
		this.#setConfig(await api.getConfig());
		this.connect();
		this.refreshMedia();
		this.refreshStatus();
		setInterval(() => this.refreshStatus(), 3000);
	}

	// --- Server events ---------------------------------------------------

	connect() {
		const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
		const ws = new WebSocket(`${protocol}://${location.host}/ws`);
		ws.onopen = () => (this.connected = true);
		ws.onmessage = (e) => this.#handle(JSON.parse(e.data));
		ws.onclose = () => {
			this.connected = false;
			setTimeout(() => this.connect(), 1000);
		};
	}

	#handle(event: ServerEvent) {
		switch (event.type) {
			case 'config':
				// Don't overwrite edits that haven't been saved yet: only take the counters.
				if (this.saveState === 'saved') this.#setConfig(event.config);
				else this.#mergeCounts(event.config.words);
				break;

			case 'transcription': {
				const last = this.transcript.at(-1);
				if (last && !last.final) {
					last.text = event.text;
					last.final = event.final;
				} else if (event.text) {
					this.transcript.push({ id: this.#nextId++, text: event.text, final: event.final });
				}
				if (this.transcript.length > MAX_LINES) this.transcript.splice(0, 1);
				break;
			}

			case 'detection':
				this.#mergeCounts([event.word]);
				this.detections.unshift({
					id: this.#nextId++,
					word: event.word.word,
					count: event.word.count,
					at: new Date()
				});
				this.detections.length = Math.min(this.detections.length, 20);
				break;

			case 'error':
				this.refreshStatus();
				break;
		}
	}

	#setConfig(config: Config) {
		this.#savedJson = serialize(config);
		this.config = config;
		i18n.locale = config.language;
	}

	#mergeCounts(words: Word[]) {
		for (const incoming of words) {
			const word = this.config?.words.find((w) => w.id === incoming.id);
			if (word) word.count = incoming.count;
		}
	}

	// --- Saving ----------------------------------------------------------

	/** Called by the page on every change of the config (see +page.svelte). */
	configChanged() {
		if (!this.config || serialize(this.config) === this.#savedJson) return;
		this.saveState = 'pending';
		clearTimeout(this.#saveTimer);
		this.#saveTimer = setTimeout(() => this.#save(), SAVE_DELAY);
	}

	async #save() {
		if (!this.config) return;
		const snapshot = $state.snapshot(this.config) as Config;
		const json = serialize(snapshot);
		this.saveState = 'saving';
		this.#savePromise = api
			.saveConfig(snapshot)
			.then((saved) => {
				this.#savedJson = json;
				this.#mergeCounts(saved.words);
				this.saveError = null;
				// Edited again while saving: a new save is already scheduled.
				this.saveState = serialize(this.config!) === json ? 'saved' : 'pending';
			})
			.catch((error: Error) => {
				this.saveState = 'error';
				this.saveError = error.message;
			})
			.finally(() => (this.#savePromise = null));
		await this.#savePromise;
	}

	/** Saves right away (e.g. before testing a punishment that was just edited). */
	async flush() {
		if (this.saveState === 'pending') {
			clearTimeout(this.#saveTimer);
			await this.#save();
		} else if (this.#savePromise) {
			await this.#savePromise;
		}
	}

	// --- Other data ------------------------------------------------------

	async refreshStatus() {
		try {
			this.status = await api.status();
		} catch {
			this.status = null;
		}
	}

	async refreshMedia() {
		this.media = await api.media();
	}
}

export const app = new AppState();
