import type {
	Config,
	MatchRequest,
	MediaFile,
	Microphones,
	PunishmentTest,
	ScreenInfo,
	Status,
	UpdateState
} from './types';

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
	const isForm = body instanceof FormData;
	const res = await fetch(path, {
		method,
		headers: body !== undefined && !isForm ? { 'Content-Type': 'application/json' } : undefined,
		body: isForm ? body : body !== undefined ? JSON.stringify(body) : undefined
	});
	if (!res.ok) {
		const error = await res.json().catch(() => null);
		const detail = error?.detail;
		throw new Error(
			typeof detail === 'string'
				? detail
				: detail
					? JSON.stringify(detail)
					: `${res.status} ${res.statusText}`
		);
	}
	return res.json();
}

export const api = {
	getConfig: () => request<Config>('GET', '/api/config'),
	saveConfig: (config: Config) => request<Config>('PUT', '/api/config', config),
	resetCount: (wordId: string) => request('POST', `/api/words/${encodeURIComponent(wordId)}/reset`),

	status: () => request<Status>('GET', '/api/status'),
	microphones: () => request<Microphones>('GET', '/api/microphones'),
	screens: () => request<ScreenInfo[]>('GET', '/api/screens'),

	media: () => request<MediaFile[]>('GET', '/api/media'),
	uploadMedia: (file: File) => {
		const form = new FormData();
		form.append('file', file);
		return request<MediaFile>('POST', '/api/media', form);
	},
	deleteMedia: (file: string) => request('DELETE', `/api/media/${encodeURIComponent(file)}`),

	testPunishment: (id: string) =>
		request<PunishmentTest>('POST', `/api/punishments/${encodeURIComponent(id)}/test`),
	/** Pauses detection (the panel repeats this every few seconds while learning a word). */
	update: () => request<UpdateState>('GET', '/api/update'),
	checkUpdate: () => request<UpdateState>('POST', '/api/update/check'),
	installUpdate: () => request<UpdateState>('POST', '/api/update/install'),
	setPaused: (paused: boolean) => request<Status>('POST', '/api/pause', { paused }),
	setLearning: (active: boolean) =>
		request<{ learning: boolean }>('POST', '/api/learning', { active }),
	phonemize: (texts: string[]) =>
		request<{ sounds: string[] }>('POST', '/api/phonemize', { texts }),
	/** Dry run: which texts would trigger this word. No punishment, no counter. */
	match: (word: MatchRequest) => request<{ matches: boolean[] }>('POST', '/api/match', word),
	simulate: (text: string) => request<{ triggered: string[] }>('POST', '/api/simulate', { text })
};

export const mediaUrl = (file: string) => `/media/${encodeURIComponent(file)}`;

export const newId = (prefix: string) => `${prefix}-${crypto.randomUUID().slice(0, 8)}`;
