import { describe, expect, it } from 'vitest';
import { highlight, tokenize, type Token } from './cssHighlight';

/** Tokens without the plain text in between, as "type:text". */
const colored = (css: string) =>
	tokenize(css)
		.filter((t: Token) => t.type !== 'text')
		.map((t) => `${t.type}:${t.text}`);

describe('tokenize', () => {
	it('never loses or adds a character', () => {
		const css = `/* c */ .word:hover > .text, #a[x="}"] { color: #fff !important; --x: var(--c, 1.5rem); }
@keyframes k { 50% { transform: translateX(-.15em) } }
@media (max-width: 100px) { body { content: "a;b" } }
.unfinished { colo`;
		expect(
			tokenize(css)
				.map((t) => t.text)
				.join('')
		).toBe(css);
	});

	it('colors a rule', () => {
		expect(colored('.word:hover { color: #00f0ff; }')).toEqual([
			'class:.word',
			'pseudo::hover',
			'punct:{',
			'property:color',
			'punct::',
			'color:#00f0ff',
			'punct:;',
			'punct:}'
		]);
	});

	it('colors values', () => {
		expect(colored('a { --c: var(--alert) !important; margin: -.5em 0 10%; }')).toEqual([
			'selector:a',
			'punct:{',
			'variable:--c',
			'punct::',
			'function:var',
			'punct:(',
			'variable:--alert',
			'punct:)',
			'important:!important',
			'punct:;',
			'property:margin',
			'punct::',
			'number:-.5em',
			'number:0',
			'number:10%',
			'punct:;',
			'punct:}'
		]);
	});

	it('colors at-rules, keyframe steps and strings', () => {
		expect(colored('@keyframes k { 50% { content: "x;y" } }')).toEqual([
			'at:@keyframes',
			'keyword:k',
			'punct:{',
			'selector:50%',
			'punct:{',
			'property:content',
			'punct::',
			'string:"x;y"',
			'punct:}',
			'punct:}'
		]);
	});

	it('keeps an unclosed comment as a comment', () => {
		expect(colored('a {} /* to do')).toEqual([
			'selector:a',
			'punct:{',
			'punct:}',
			'comment:/* to do'
		]);
	});
});

describe('highlight', () => {
	it('escapes HTML', () => {
		expect(highlight('a > b { content: "<b>&" }')).not.toMatch(/<b>|&"/);
		expect(highlight('a > b')).toContain('&gt;');
	});
});
