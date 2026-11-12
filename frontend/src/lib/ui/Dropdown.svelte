<!--
	A button that opens a menu of choices, in the theme's style (terminal-like entries).
	Esc or a click outside closes it; arrows move between entries.
	The menu is a sibling of the button, not its child: the button's cut-corner mask would clip it.
-->
<script lang="ts" generics="T extends string">
	import { tick } from 'svelte';

	let {
		label,
		items,
		onselect
	}: {
		label: string;
		items: { value: T; label: string; hint?: string }[];
		onselect: (value: T) => void;
	} = $props();

	let open = $state(false);
	let root = $state<HTMLDivElement>();
	let trigger = $state<HTMLButtonElement>();

	const entries = () => [...(root?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? [])];

	async function toggle() {
		open = !open;
		if (open) {
			await tick();
			entries()[0]?.focus();
		}
	}

	function close(refocus = false) {
		open = false;
		if (refocus) trigger?.focus();
	}

	function choose(value: T) {
		close(true);
		onselect(value);
	}

	function onkeydown(e: KeyboardEvent) {
		if (!open) return;
		if (e.key === 'Escape') {
			e.preventDefault();
			e.stopPropagation(); // not also the Esc of an enclosing dialog
			close(true);
		} else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
			e.preventDefault();
			const list = entries();
			const index = list.indexOf(document.activeElement as HTMLElement);
			const step = e.key === 'ArrowDown' ? 1 : -1;
			list[(index + step + list.length) % list.length]?.focus();
		} else if (e.key === 'Tab') {
			close(); // focus moves on naturally
		}
	}
</script>

<svelte:window
	onpointerdown={(e) => {
		if (open && root && !root.contains(e.target as Node)) close();
	}}
/>

<div class="relative" bind:this={root} {onkeydown} role="presentation">
	<button
		bind:this={trigger}
		type="button"
		class="key-primary"
		aria-haspopup="menu"
		aria-expanded={open}
		onclick={toggle}
	>
		+ {label} <span aria-hidden="true">{open ? '▴' : '▾'}</span>
	</button>

	{#if open}
		<div
			role="menu"
			class="absolute top-full right-0 z-20 mt-1.5 flex min-w-64 flex-col gap-0.5 p-1 recess"
			style="box-shadow: 0 0 1.25rem rgb(0 240 255 / 0.2), inset 0 0 0.75rem rgb(0 240 255 / 0.08);"
		>
			{#each items as item (item.value)}
				<button
					type="button"
					role="menuitem"
					class="nav-item outline-none focus-visible:border-accent focus-visible:bg-accent/10 focus-visible:text-fg"
					onclick={() => choose(item.value)}
				>
					<span class="min-w-0">
						<span class="block">{item.label}</span>
						{#if item.hint}
							<span class="block text-xs font-normal tracking-normal text-muted normal-case">
								{item.hint}
							</span>
						{/if}
					</span>
				</button>
			{/each}
		</div>
	{/if}
</div>
