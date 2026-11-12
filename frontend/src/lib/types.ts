// Mirrors backend/config.py

export type Mode = 'phonetic' | 'exact';
export type Strategy = 'all' | 'random' | 'escalation';
export type MediaType = 'sound' | 'image' | 'video';
export type WordDisplayMode = 'shown' | 'hidden' | 'partial';
export type WordsAlign = 'left' | 'center' | 'right';
export type WordsPosition = 'top' | 'middle' | 'bottom';

export interface ChromaKey {
	enabled: boolean;
	color: string;
	similarity: number;
	smoothness: number;
	spill: number;
}

export interface Punishment {
	id: string;
	name: string;
	type: MediaType;
	file: string;
	volume: number;
	duration: number;
	chroma_key: ChromaKey;
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
	punishments: { strategy: Strategy; ids: string[] };
}

export interface Config {
	language: 'en' | 'fr';
	microphone: string | number | null;
	model: string;
	cooldown: number;
	display: {
		screen: { enabled: boolean; monitor: number; sound: boolean; hide_from_capture: boolean };
		overlay: { sound: boolean };
		words: {
			font_size: number;
			color: string;
			align: WordsAlign;
			position: WordsPosition;
			show_count: boolean;
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

export interface Status {
	listening: boolean;
	microphone: string | null;
	listener_error: string | null;
	phonetics_error: string | null;
}

export type ServerEvent =
	| { type: 'config'; config: Config }
	| { type: 'transcription'; text: string; final: boolean }
	| { type: 'detection'; word: Word }
	| { type: 'punishment'; punishment: Punishment; word: string | null }
	| { type: 'error'; message: string };
