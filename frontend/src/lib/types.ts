// Mirrors backend/config.py

export type Mode = 'phonetic' | 'exact';
export type Strategy = 'all' | 'random' | 'escalation';
export type MediaType = 'sound' | 'image' | 'video';
export type PunishmentType = MediaType | 'add_word';
export type WordDisplayMode = 'shown' | 'hidden' | 'partial';
export type WordsAlign = 'left' | 'center' | 'right';
export type WordsPosition = 'top' | 'middle' | 'bottom';
export type EnterAnimation = 'none' | 'fade' | 'slide' | 'pop' | 'glitch';
export type ExitAnimation = 'none' | 'fade' | 'slide' | 'shrink' | 'glitch';
export type HitAnimation = 'none' | 'shake' | 'pulse' | 'flash' | 'glitch';

export interface ChromaKey {
	enabled: boolean;
	color: string;
	similarity: number;
	smoothness: number;
	spill: number;
}

export interface PunishmentSelection {
	strategy: Strategy;
	ids: string[];
}

/** Options of the "add a forbidden word" punishment. */
export interface AddWordSettings {
	pool: string[];
	mode: Mode;
	display_mode: WordDisplayMode;
	punishments_from: 'trigger' | 'list';
	punishments: PunishmentSelection;
	duration: number; // seconds, 0 = until removed by hand
}

export interface Punishment {
	id: string;
	name: string;
	type: PunishmentType;
	file: string;
	volume: number;
	duration: number;
	chroma_key: ChromaKey;
	add_word: AddWordSettings;
}

export interface Word {
	id: string;
	word: string;
	mode: Mode;
	word_end: boolean;
	word_start: boolean;
	plural: boolean;
	enabled: boolean;
	count: number;
	display_mode: WordDisplayMode;
	/** What Vosk transcribes when the word is said (it can't output invented words). */
	variants: string[];
	/** Phonetic mode: how many sounds may differ (0 to 2). */
	tolerance: number;
	punishments: PunishmentSelection;
	/** Added by a punishment: the server decides when it exists. */
	auto: boolean;
	expires_at: number | null; // Unix time, in seconds
}

export interface Config {
	language: 'en' | 'fr';
	microphone: string | number | null;
	model: string;
	cooldown: number;
	max_active_words: number;
	display: {
		screen: { enabled: boolean; monitor: number; sound: boolean; hide_from_capture: boolean };
		overlay: { sound: boolean };
		words: {
			font_size: number;
			color: string;
			align: WordsAlign;
			position: WordsPosition;
			show_count: boolean;
			enter_animation: EnterAnimation;
			exit_animation: ExitAnimation;
			hit_animation: HitAnimation;
			custom_css_enabled: boolean;
			custom_css: string;
		};
	};
	words: Word[];
	punishments: Punishment[];
}

export interface MediaFile {
	file: string;
	type: MediaType;
	size: number;
}

export interface Microphones {
	default: string | null;
	microphones: { id: string; label: string }[];
}

export interface ScreenInfo {
	index: number;
	name: string;
	width: number;
	height: number;
	primary: boolean;
}

export type AddWordResult = 'added' | 'no_candidate' | 'max_reached';

/** What the server answers to "test this punishment". */
export interface PunishmentTest {
	ok: true;
	result: 'played' | AddWordResult;
	word?: string;
}

/** A word as it is being edited (not saved), to try on sentences. */
export interface MatchRequest {
	word: string;
	mode: Mode;
	word_start: boolean;
	word_end: boolean;
	plural: boolean;
	variants: string[];
	tolerance: number;
	texts: string[];
}

export interface Status {
	listening: boolean;
	microphone: string | null;
	listener_error: string | null;
	phonetics_error: string | null;
	/** The "learn a word" window is open: speech is shown but not detected. */
	learning: boolean;
}

export type ServerEvent =
	| { type: 'config'; config: Config }
	| { type: 'transcription'; text: string; final: boolean }
	| { type: 'detection'; word: Word }
	| { type: 'punishment'; punishment: Punishment; word: string | null }
	| { type: 'error'; message: string };
