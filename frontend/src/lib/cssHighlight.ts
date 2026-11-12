/**
 * Small CSS tokenizer for syntax coloring (custom CSS of the words overlay).
 * Not a parser: it only needs to color what people type, including half-written rules.
 *
 * The text is cut into segments ending with "{", ";" or "}":
 * - a segment ending with "{" is a selector (or an at-rule prelude such as "@media …"),
 * - any other segment is a declaration "property: value" (or "@import …;").
 */

export type TokenType =
	| 'comment'
	| 'punct'
	| 'selector' // tag, *, keyframe steps (from, 50%)
	| 'class' // .class, #id
	| 'pseudo' // :hover, ::before
	| 'attr' // [data-x="y"]
	| 'at' // @media, @keyframes
	| 'property'
	| 'variable' // --custom-property
	| 'number' // 1.5rem, 50%, 0
	| 'color' // #ff2bd6
	| 'string'
	| 'function' // var(, translateX(
	| 'important'
	| 'keyword' // other identifiers in values: flex, solid, red…
	| 'text'; // spaces, unknown characters

export interface Token {
	type: TokenType;
	text: string;
}

const SELECTOR =
	/(?<class>[.#][\w-]+)|(?<pseudo>::?[\w-]+)|(?<attr>\[[^\]]*\]?)|(?<selector>[\w%-]+|\*)|(?<punct>[,>+~()])/y;

const VALUE =
	/(?<string>"[^"]*"?|'[^']*'?)|(?<important>!\s*important\b)|(?<color>#[\da-fA-F]{3,8}\b)|(?<number>-?(?:\d+\.?\d*|\.\d+)(?:%|[a-zA-Z]+)?)|(?<variable>--[\w-]+)|(?<function>[\w-]+(?=\())|(?<keyword>[\w-]+)|(?<punct>[(),/:])/y;

/** Applies a sticky regex with named groups along the text; unmatched characters become "text". */
function scan(text: string, pattern: RegExp, out: Token[]): void {
	let i = 0;
	while (i < text.length) {
		pattern.lastIndex = i;
		const match = pattern.exec(text);
		const type = match?.groups && Object.entries(match.groups).find(([, v]) => v !== undefined);
		if (match && type) {
			push(out, type[0] as TokenType, match[0]);
			i += match[0].length;
		} else {
			push(out, 'text', text[i]);
			i += 1;
		}
	}
}

/** Adds a token, merging consecutive plain text. */
function push(out: Token[], type: TokenType, text: string): void {
	const last = out.at(-1);
	if (type === 'text' && last?.type === 'text') last.text += text;
	else out.push({ type, text });
}

function atRule(segment: string, out: Token[]): void {
	const name = /^\s*@[\w-]*/.exec(segment)![0];
	push(out, 'at', name);
	scan(segment.slice(name.length), VALUE, out);
}

function declaration(segment: string, out: Token[]): void {
	if (/^\s*@/.test(segment)) return atRule(segment, out);
	const colon = segment.indexOf(':');
	if (colon < 0) {
		// Still being typed ("colo"): a property name
		const property = /^(\s*)([\s\S]*)$/.exec(segment)!;
		push(out, 'text', property[1]);
		if (property[2]) push(out, property[2].startsWith('--') ? 'variable' : 'property', property[2]);
		return;
	}
	const [, before, name, after] = /^(\s*)(\S*?)(\s*)$/.exec(segment.slice(0, colon))!;
	push(out, 'text', before);
	if (name) push(out, name.startsWith('--') ? 'variable' : 'property', name);
	push(out, 'text', after);
	push(out, 'punct', ':');
	scan(segment.slice(colon + 1), VALUE, out);
}

export function tokenize(css: string): Token[] {
	const out: Token[] = [];
	let i = 0;
	while (i < css.length) {
		if (css.startsWith('/*', i)) {
			const end = css.indexOf('*/', i + 2);
			const stop = end < 0 ? css.length : end + 2;
			push(out, 'comment', css.slice(i, stop));
			i = stop;
			continue;
		}
		// Segment up to the next "{", ";", "}" or comment, ignoring those inside strings
		let j = i;
		let quote = '';
		while (j < css.length) {
			const c = css[j];
			if (quote) {
				if (c === quote) quote = '';
			} else if (c === '"' || c === "'") quote = c;
			else if ('{;}'.includes(c) || css.startsWith('/*', j)) break;
			j++;
		}
		const segment = css.slice(i, j);
		const end = css[j];
		if (segment) {
			if (end === '{') {
				if (/^\s*@/.test(segment)) atRule(segment, out);
				else scan(segment, SELECTOR, out);
			} else if (/^\s*$/.test(segment)) push(out, 'text', segment);
			else declaration(segment, out);
		}
		if (end && '{;}'.includes(end)) {
			push(out, 'punct', end);
			j++;
		}
		i = j;
	}
	return out;
}

const ESCAPES: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' };
const escape = (text: string) => text.replace(/[&<>"]/g, (c) => ESCAPES[c]);

/** HTML with one <span class="tok-TYPE"> per token, text escaped. */
export function highlight(css: string): string {
	return tokenize(css)
		.map((t) =>
			t.type === 'text' ? escape(t.text) : `<span class="tok-${t.type}">${escape(t.text)}</span>`
		)
		.join('');
}
